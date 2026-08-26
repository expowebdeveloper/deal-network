import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { BrandMark, CheckIcon, CrossIcon, ClockIcon } from '../icons/Icons'
import {
  confirmCheckout, isBillingUnconfigured, billingErrorMessage, signupIntent,
} from '../../lib/billing'

/**
 * Where Stripe sends the browser after a successful payment —
 * `STRIPE_SUCCESS_PATH?session_id=cs_…`, which is `/billing/success` by default.
 *
 * The subtlety this screen exists to handle: **Stripe redirects the browser and
 * calls our webhook at the same time, and the browser usually wins the race.**
 * If this page simply said "you're all set" it would sometimes be lying, and if
 * it only waited for the webhook it would sometimes spin for no reason.
 *
 * So it asks the server to confirm the session directly. The server reads the
 * session from Stripe, checks it belongs to this member, and applies it — the
 * same write the webhook performs, from the same source, so whichever lands
 * second changes nothing.
 *
 * `activated: false` is a legitimate answer rather than a failure: some payment
 * methods settle asynchronously. In that case this polls a few times and then
 * hands over to the webhook, telling the member their plan will switch on
 * shortly instead of pretending it already has.
 */

const MAX_ATTEMPTS = 6
const RETRY_MS = 2000

/**
 * Whether waiting and asking again could plausibly change the answer.
 *
 * Only a lost connection or a gateway hiccup qualifies. A refusal is settled —
 * and `BILLING_NOT_CONFIGURED` in particular arrives as a 503, which a naive
 * "retry any 5xx" rule would spin on for twelve seconds before admitting that
 * the server has no Stripe keys and never will during this page load.
 */
function isRetryable(error) {
  if (isBillingUnconfigured(error)) return false
  const status = error?.status
  return status === 0 || status === 502 || status === 504
}

export default function BillingReturn() {
  const { loadSession } = useApp()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const sessionId = params.get('session_id')

  const timer = useRef(null)
  const [state, setState] = useState({ status: 'confirming', attempt: 1, error: null, plan: null })

  /** Where a member goes once their plan is live. */
  const continueIntoApp = useCallback(async () => {
    let me = null
    try {
      me = await loadSession()
    } catch {
      /* the session call failed; the router will send them somewhere sensible */
    }
    signupIntent.clear()
    if (!me) navigate('/', { replace: true })
    else if (!me.terms_accepted) navigate('/terms', { replace: true })
    else navigate(me.onboarded ? '/' : '/onboarding', { replace: true })
  }, [loadSession, navigate])

  useEffect(() => {
    // Someone opened this URL directly, or Stripe was configured with a success
    // path that drops the parameter. Nothing to confirm.
    if (!sessionId) {
      navigate('/plans', { replace: true })
      return
    }

    // Guarded by `cancelled` alone, deliberately — no "have I already started"
    // ref. StrictMode mounts, unmounts and remounts in development: a ref guard
    // makes the second mount skip the work while the first mount's cleanup has
    // already set its own `cancelled`, so nothing ever resolves and the page
    // spins on "Confirming…" for good.
    //
    // Letting both runs call through is safe because confirm-checkout is
    // idempotent server-side — it re-applies the same state from the same Stripe
    // session — and the stale run cannot touch state once cancelled.
    let cancelled = false
    let attempt = 0

    async function attemptConfirm() {
      attempt += 1
      if (cancelled) return
      setState((s) => ({ ...s, status: 'confirming', attempt }))

      try {
        const result = await confirmCheckout(sessionId)
        if (cancelled) return

        if (result.activated) {
          setState({ status: 'done', attempt, error: null, plan: result.plan })
          return
        }

        // Paid but not settled, or still processing at Stripe.
        if (attempt < MAX_ATTEMPTS) {
          timer.current = setTimeout(attemptConfirm, RETRY_MS)
          return
        }
        setState({ status: 'pending', attempt, error: null, plan: result.plan })
      } catch (error) {
        if (cancelled) return
        if (isRetryable(error) && attempt < MAX_ATTEMPTS) {
          timer.current = setTimeout(attemptConfirm, RETRY_MS)
          return
        }
        setState({
          status: 'error',
          attempt,
          plan: null,
          error: isBillingUnconfigured(error)
            ? 'Card payments are not switched on for this environment.'
            : billingErrorMessage(error, 'We could not confirm the payment.'),
        })
      }
    }

    attemptConfirm()
    return () => {
      cancelled = true
      if (timer.current) clearTimeout(timer.current)
    }
  }, [sessionId, navigate])

  // Once confirmed, refresh the session and move on. Kept out of the effect
  // above so the redirect happens after the tick that paints "Payment received".
  useEffect(() => {
    if (state.status !== 'done') return
    const handle = setTimeout(continueIntoApp, 1200)
    return () => clearTimeout(handle)
  }, [state.status, continueIntoApp])

  return (
    <div className="billing-return">
      <BrandMark />

      {state.status === 'confirming' && (
        <div className="br-panel">
          <div className="br-spinner" aria-hidden="true" />
          <h1>Confirming your payment…</h1>
          <p>
            This takes a second. Please do not close this window.
            {state.attempt > 1 && (
              <> Still checking — attempt {state.attempt} of {MAX_ATTEMPTS}.</>
            )}
          </p>
        </div>
      )}

      {state.status === 'done' && (
        <div className="br-panel">
          <div className="br-icon ok"><CheckIcon /></div>
          <h1>Payment received</h1>
          <p>Your plan is live. Taking you into Deal Network…</p>
        </div>
      )}

      {state.status === 'pending' && (
        <div className="br-panel">
          <div className="br-icon wait"><ClockIcon /></div>
          <h1>Payment is being processed</h1>
          <p>
            Your bank has not finished settling the payment. We will switch your
            plan on automatically as soon as it clears, and email you when it
            does — there is nothing else for you to do.
          </p>
          <div className="br-actions">
            <button className="btn btn-primary" onClick={continueIntoApp}>
              Continue to Deal Network
            </button>
          </div>
        </div>
      )}

      {state.status === 'error' && (
        <div className="br-panel">
          <div className="br-icon bad"><CrossIcon /></div>
          <h1>We could not confirm the payment</h1>
          <p>{state.error}</p>
          <p className="br-note">
            If you were charged, nothing is lost — your plan switches on as soon
            as we hear from Stripe. Your card is never stored by Deal Network.
          </p>
          <div className="br-actions">
            <button className="btn btn-ghost" onClick={() => navigate('/plans', { replace: true })}>
              Back to plans
            </button>
            <button className="btn btn-primary" onClick={continueIntoApp}>
              Continue anyway
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
