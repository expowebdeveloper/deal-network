import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Screen, { PageHead } from '../layout/Screen'
import { Loading, ErrorState } from '../ui/States'
import { InfoIcon, CheckIcon, CrossIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import { listPlans, selectPlan } from '../../lib/feed'
import {
  FREE_PLAN, isPaidPlan, activateSignup, signupIntent, goToStripe,
  isBillingUnconfigured, billingErrorMessage,
} from '../../lib/billing'

function Feature({ feature }) {
  return (
    <li className={feature.included ? undefined : 'off'}>
      {feature.included ? <CheckIcon /> : <CrossIcon />}
      {feature.label}
    </li>
  )
}

/**
 * `onboarding` is set when the member has not chosen a plan yet — the app is
 * locked to this screen until they do (the API enforces it as well).
 */
export default function Plans({ onboarding = false }) {
  const { loadSession, currentPlan, openModal } = useApp()
  const navigate = useNavigate()

  const [state, setState] = useState({ status: 'loading', plans: [], error: null })
  const [choosing, setChoosing] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setState((s) => ({ ...s, status: 'loading' }))
    try {
      setState({ status: 'ready', plans: await listPlans(), error: null })
    } catch (err) {
      setState({ status: 'error', plans: [], error: err })
    }
  }, [])

  useEffect(() => { load() }, [load])

  /**
   * A plan chosen on the public pricing page arrives as a signup intent held
   * server-side. Spending it is what starts Checkout, so it is tried before the
   * plain "choose a plan" path — otherwise a visitor who picked Member on the
   * way in would silently land on the free tier.
   *
   * Takes no plan argument on purpose: the tier is whatever the server recorded
   * when the intent was created, which is the point of holding it server-side.
   *
   * Returns true when it took over; false when there was no pending intent, or
   * it had expired and the member should just pick again.
   */
  async function spendPendingIntent() {
    const intentId = signupIntent.get()
    if (!intentId) return false
    try {
      const result = await activateSignup(intentId)
      signupIntent.clear()
      if (result.checkout_url) {
        goToStripe(result.checkout_url)
        return true
      }
      const me = await loadSession()
      navigate(me?.onboarded ? '/' : '/onboarding', { replace: true })
      return true
    } catch (err) {
      // An expired or already-spent intent is not an error worth showing —
      // fall through and treat this as a fresh choice.
      signupIntent.clear()
      if (isBillingUnconfigured(err)) {
        setError(
          'Card payments are not switched on for this environment yet. '
          + 'Early access is free and available now.',
        )
        return true
      }
      return false
    }
  }

  async function choose(plan) {
    if (choosing) return
    setChoosing(plan.id)
    setError(null)
    try {
      if (await spendPendingIntent()) return

      if (isPaidPlan(plan.id)) {
        // Paid tiers are never granted here. The modal confirms the amount and
        // hands the browser to Stripe; the plan switches on when the payment
        // clears and the webhook lands.
        openModal('checkout', {
          plan: plan.id,
          name: plan.name,
          price: String(plan.price ?? '').replace(/^\$/, ''),
          interval: plan.per || '/month',
        })
        return
      }

      await selectPlan(plan.id)
      // Re-read /api/me so the gate opens and the plan updates, then on to the
      // next step: profile setup for a new member, the app for everyone else.
      const me = await loadSession()
      navigate(me?.onboarded ? '/' : '/onboarding', { replace: true })
    } catch (err) {
      setError(billingErrorMessage(err, err.message))
    } finally {
      setChoosing(null)
    }
  }

  return (
    <Screen name="plans">
      <PageHead title={onboarding ? 'Choose your plan' : 'Plans'}>
        {onboarding
          ? 'Pick a plan to finish setting up your account. Early access is free and you can change later.'
          : 'Two paid tiers, plus the early-access period you are on right now.'}
      </PageHead>

      {onboarding ? (
        <div className="gate-bar">
          <InfoIcon />
          <div>
            <h4>One more step before you can explore</h4>
            <p>
              Choose a plan to unlock your feed, communities and contacts. Early access is free,
              needs no card, and you can move to a paid tier whenever you like.
            </p>
          </div>
        </div>
      ) : (
        <div className="earlybar">
          <InfoIcon />
          <div>
            <h4>You are on early access — nothing to pay yet</h4>
            <p>
              Paid plans switch on once the network reaches critical mass in your markets. Everyone
              who joins before then keeps early-access pricing when it does.
            </p>
          </div>
        </div>
      )}

      {error && <div className="inline-error">{error}</div>}

      {state.status === 'loading' && <Loading label="Loading plans…" />}
      {state.status === 'error' && <ErrorState error={state.error} onRetry={load} />}

      {state.status === 'ready' && (
        <div className="plans">
          {state.plans.map((plan) => {
            const isCurrent = !onboarding && plan.id === currentPlan
            // A paid tier with no Stripe Price configured on the server cannot be
            // bought. Say so on the card instead of offering a button that can
            // only end in "card payments are not switched on".
            const unavailable = plan.purchasable === false && !isCurrent
            return (
              <div className={`card plan${plan.featured ? ' feat' : ''}`} key={plan.id}>
                {isCurrent ? (
                  <span className="plan-badge cur">CURRENT</span>
                ) : plan.featured ? (
                  <span className="plan-badge">MOST POPULAR</span>
                ) : null}

                <h3>{plan.name}</h3>
                <div className="for">{plan.tagline}</div>
                <div className="price">
                  <span className="amt">{plan.price}</span>
                  {plan.per && <span className="per">{plan.per}</span>}
                </div>
                <div className="billed">{plan.billed}</div>

                <ul>
                  {plan.features.map((f) => <Feature key={f.label} feature={f} />)}
                </ul>

                {/* One lime button per screen: the plan we recommend, or the one
                    already yours. The rest are quiet so it stays a choice. */}
                <button
                  className={`btn btn-${isCurrent || (plan.featured && !unavailable) ? 'primary' : 'ghost'} btn-block`}
                  data-busy={choosing === plan.id}
                  disabled={unavailable}
                  title={unavailable
                    ? 'Card payments are not switched on for this environment yet.'
                    : undefined}
                  onClick={() => choose(plan)}
                >
                  {choosing === plan.id
                    ? 'Selecting…'
                    : isCurrent
                      ? `Continue with ${plan.name}`
                      : unavailable
                        ? 'Not available yet'
                        : plan.id === FREE_PLAN
                          ? 'Choose plan'
                          /* Say where the button goes: a paid tier leaves the app
                             for Stripe's page, which is not what "Choose" implies. */
                          : `Subscribe — ${plan.price}${plan.per || ''}`}
                </button>

                {unavailable && (
                  <p className="plan-unavailable">
                    Paid plans are not switched on in this environment yet. Early
                    access is free and available now.
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </Screen>
  )
}
