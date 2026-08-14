import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Screen, { PageHead } from '../layout/Screen'
import { Loading, ErrorState } from '../ui/States'
import { InfoIcon, CheckIcon, CrossIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import { listPlans, selectPlan } from '../../lib/feed'

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
  const { loadSession, currentPlan } = useApp()
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

  async function choose(plan) {
    if (choosing) return
    setChoosing(plan.id)
    setError(null)
    try {
      await selectPlan(plan.id)
      // Re-read /api/me so the gate opens and the plan updates, then on to the
      // next step: profile setup for a new member, the app for everyone else.
      const me = await loadSession()
      navigate(me?.onboarded ? '/' : '/onboarding', { replace: true })
    } catch (err) {
      setError(err.message)
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
                  className={`btn btn-${isCurrent || plan.featured ? 'primary' : 'ghost'} btn-block`}
                  data-busy={choosing === plan.id}
                  onClick={() => choose(plan)}
                >
                  {choosing === plan.id
                    ? 'Selecting…'
                    : isCurrent
                      ? `Continue with ${plan.name}`
                      : 'Choose plan'}
                </button>
              </div>
            )
          })}
        </div>
      )}
    </Screen>
  )
}
