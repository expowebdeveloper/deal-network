/**
 * Billing client for the /api/v1/billing surface.
 *
 * The one thing to understand about this file: **no card details pass through
 * it, and there is no card form anywhere in this app.** Paying means being
 * redirected to Stripe's own hosted Checkout page. The card is typed into
 * Stripe's page, on Stripe's domain, and what comes back to us is a session id
 * plus the last four digits.
 *
 * That is not only a security preference — it is what keeps this codebase out of
 * PCI-DSS scope. A card number typed into our own form would put every server it
 * touches in scope, even if we never stored it.
 *
 * The flow, end to end:
 *
 *   anonymous visitor picks a paid plan
 *     -> createSignupIntent(plan)        the choice is held server-side
 *     -> startOAuth(provider, intentId)  sign in, intent rides in signed state
 *     -> activateSignup(intentId)        returns a Stripe checkout_url
 *     -> window.location = checkout_url  Stripe's page
 *     -> Stripe redirects to /billing/success?session_id=…
 *     -> confirmCheckout(sessionId)      applies it; the webhook agrees
 *
 * A member who is already signed in skips the middle and calls startCheckout().
 */

import { api, request, ApiError, API_URL } from './api'

/* --- The price list ------------------------------------------------------- */

/** Readable without an account — it is the public pricing page. */
export function fetchBillingPlans() {
  return request('/api/v1/billing/plans', { auth: false })
}

export function fetchBillingPlan(code) {
  return request(`/api/v1/billing/plans/${code}`, { auth: false })
}

/* --- Choosing a plan before there is an account --------------------------- */

/**
 * Hold a plan choice server-side before signup (backend_flow.md 7.1).
 * Returns `{ signup_intent_id, plan_code, expires_at }`.
 */
export function createSignupIntent(planCode, email) {
  return request('/api/v1/billing/signup-intent', {
    method: 'POST',
    body: { plan_code: planCode, ...(email ? { email } : {}) },
    auth: false,
  })
}

/**
 * Full-page handoff to the backend, which redirects on to Google/Apple.
 *
 * The intent id is passed as a query parameter here but the backend folds it
 * into the *signed* OAuth state before sending the browser onward, so it cannot
 * be swapped for a more expensive tier in transit.
 */
export function startOAuthWithIntent(provider, signupIntentId) {
  const query = signupIntentId ? `?signup_intent=${encodeURIComponent(signupIntentId)}` : ''
  window.location.href = `${API_URL}/auth/${provider}/login${query}`
}

/**
 * Spend the held choice on the freshly created account.
 *
 * Early Access comes back `{ activated: true }` and is live immediately.
 * A paid tier comes back `{ activated: false, checkout_url }` — nothing is
 * granted until Stripe confirms the payment.
 */
export function activateSignup(signupIntentId) {
  return api.post('/api/v1/billing/activate-signup', { signup_intent_id: signupIntentId })
}

/* --- Paying --------------------------------------------------------------- */

/** Open a Checkout Session. Returns `{ checkout_url, session_id }`. */
export function startCheckout(planCode) {
  return api.post('/api/v1/billing/checkout-session', { plan_code: planCode })
}

/** Apply a finished session on the return redirect. */
export function confirmCheckout(sessionId) {
  return api.post('/api/v1/billing/confirm-checkout', { session_id: sessionId })
}

/** Stripe's hosted portal: card changes, invoices, cancellation. */
export function createPortalSession() {
  return api.post('/api/v1/billing/portal-session', {})
}

/* --- Managing an existing subscription ------------------------------------ */

export function fetchSubscription() {
  return api.get('/api/v1/billing/subscription')
}

export function fetchBillingEntitlements() {
  return api.get('/api/v1/billing/entitlements')
}

export function fetchDowngradePreview() {
  return api.get('/api/v1/billing/downgrade-preview')
}

export function changePlan(planCode) {
  return api.post('/api/v1/billing/change-plan', { plan_code: planCode })
}

export function cancelSubscription() {
  return api.post('/api/v1/billing/cancel', {})
}

export function reactivateSubscription() {
  return api.post('/api/v1/billing/reactivate', {})
}

export function fetchInvoices() {
  return api.get('/api/v1/billing/invoices')
}

/* --- Helpers -------------------------------------------------------------- */

export const FREE_PLAN = 'early_access'

export function isPaidPlan(code) {
  return code !== FREE_PLAN
}

/**
 * The /api/v1 errors use `{"error": {"code", "message", "details"}}`, which the
 * shared client does not know how to unwrap — it only reads `detail`.
 */
export function billingErrorCode(error) {
  return error instanceof ApiError ? (error.body?.error?.code ?? null) : null
}

export function billingErrorMessage(error, fallback = 'Something went wrong.') {
  if (!(error instanceof ApiError)) return error?.message || fallback
  return error.body?.error?.message || error.message || fallback
}

/**
 * True when the server has no Stripe keys. Worth its own check because it is
 * not the member's fault and must not be shown to them as a payment failure.
 */
export function isBillingUnconfigured(error) {
  return billingErrorCode(error) === 'BILLING_NOT_CONFIGURED'
}

/** Send the browser to Stripe. Full page navigation, not a fetch. */
export function goToStripe(checkoutUrl) {
  window.location.assign(checkoutUrl)
}

const INTENT_KEY = 'dn.signupIntent'

/**
 * The intent id has to survive the OAuth round trip *and* the terms screen, so
 * it is parked in sessionStorage as well as coming back in the callback
 * fragment. Whichever arrives is used; the store is the fallback for a member
 * who signed in, read the terms, and only then reached the plan step.
 */
export const signupIntent = {
  get() {
    try {
      return sessionStorage.getItem(INTENT_KEY)
    } catch {
      return null
    }
  },
  set(value) {
    try {
      if (value) sessionStorage.setItem(INTENT_KEY, value)
      else sessionStorage.removeItem(INTENT_KEY)
    } catch {
      /* private mode — the callback fragment still carries it this page load */
    }
  },
  clear() {
    this.set(null)
  },
}
