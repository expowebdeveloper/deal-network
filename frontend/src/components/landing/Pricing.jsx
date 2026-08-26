import { useCallback, useEffect, useState } from 'react'
import PublicPage from './PublicPage'
import { Loading, ErrorState } from '../ui/States'
import { CheckIcon, CrossIcon, InfoIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import { fetchPlanCatalogue } from '../../lib/feed'
import { createSignupIntent, signupIntent } from '../../lib/billing'
import { roadmap } from '../../data/landing'

/** How far up the roadmap a tier reaches. `roadmap` is the full phase list, so
    a tier that reaches the end says so rather than naming the last number. */
function phaseLabel(maxPhase) {
  if (!maxPhase) return null
  if (maxPhase >= roadmap.length) return `Roadmap access: all ${roadmap.length} phases`
  return maxPhase > 1 ? `Roadmap access: phase 1–${maxPhase}` : 'Roadmap access: phase 1 only'
}

function Feature({ feature }) {
  return (
    <li className={feature.included ? undefined : 'off'}>
      {feature.included ? <CheckIcon /> : <CrossIcon />}
      {feature.label}
    </li>
  )
}

/**
 * The public price list at `/pricing` — where Get started and the Pricing link
 * both land.
 *
 * Choosing is an account action, so the buttons here open sign-in; the same
 * plans come back as the first step after the terms, and the API is what
 * actually records the choice.
 */
export default function Pricing() {
  const { openModal } = useApp()
  const [state, setState] = useState({ status: 'loading', plans: [], error: null })
  const [picking, setPicking] = useState(null)

  const load = useCallback(async () => {
    setState((s) => ({ ...s, status: 'loading' }))
    try {
      // max_phase comes down with each plan, so the roadmap reach on the cards
      // is the server's answer rather than a second copy of the rules here.
      setState({ status: 'ready', plans: await fetchPlanCatalogue(), error: null })
    } catch (error) {
      setState({ status: 'error', plans: [], error })
    }
  }, [])

  useEffect(() => { load() }, [load])

  const signIn = () => openModal('login', {})

  /**
   * Choosing a plan here happens *before* there is an account, so the choice is
   * recorded server-side first (backend_flow.md 7.1) and its id is carried
   * through sign-in. Without that step the tier would have to travel as a query
   * parameter the visitor could edit, which is exactly what the spec rules out.
   *
   * If the intent cannot be created the sign-in dialog still opens — losing the
   * pre-selection is a small annoyance; blocking sign-up is not acceptable.
   */
  async function choosePlan(plan) {
    if (picking) return
    setPicking(plan.id)
    try {
      const intent = await createSignupIntent(plan.id)
      signupIntent.set(intent.signup_intent_id)
    } catch {
      signupIntent.clear()
    } finally {
      setPicking(null)
      openModal('login', { signupIntentPlan: plan.id })
    }
  }

  return (
    <PublicPage page="pricing" onLogin={signIn}>
      {/* Head and cards together fill the first screen — the plans are what this
          page is for, so nothing pushes them below the fold. */}
      <section className="pricing-top">
        <div className="wrap">
          <div className="pricing-head">
            <span className="eyebrow">Plans</span>
            <h1>Choose the plan that matches how you work.</h1>
            <p>
              Early access is free while we grow the first few hundred members. Paid tiers add
              the contacts, pipeline and team seats you need once deals start moving.
              <span className="pricing-note">
                <InfoIcon />
                Choosing is tied to your account — sign in and your plan is the first thing you
                pick. You can change tier later.
              </span>
            </p>
          </div>

          {state.status === 'loading' && <Loading label="Loading plans…" />}
          {state.status === 'error' && <ErrorState error={state.error} onRetry={load} />}

          {state.status === 'ready' && (
            <div className="plans">
              {state.plans.map((plan) => {
                // A paid tier with no Stripe Price configured server-side cannot
                // be bought yet; the card says so rather than sending a visitor
                // through sign-in to a payment page that cannot open.
                const unavailable = plan.purchasable === false
                return (
                <div className={`card plan${plan.featured ? ' feat' : ''}`} key={plan.id}>
                  {plan.featured && <span className="plan-badge">MOST POPULAR</span>}

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

                  <div className="plan-phase">{phaseLabel(plan.max_phase)}</div>

                  <button
                    className={`btn btn-${plan.featured && !unavailable ? 'primary' : 'ghost'} btn-block`}
                    data-busy={picking === plan.id}
                    disabled={unavailable}
                    onClick={() => choosePlan(plan)}
                  >
                    {unavailable
                      ? 'Not available yet'
                      : picking === plan.id ? 'Just a moment…' : 'Choose plan'}
                  </button>

                  {unavailable && (
                    <p className="plan-unavailable">
                      Card payments are not switched on yet. Early access is free
                      and available now.
                    </p>
                  )}
                </div>
                )
              })}
            </div>
          )}
        </div>
      </section>

      <section className="roadmap">
        <div className="wrap roadmap-head">
          <div className="section-head">
            <span className="eyebrow">What the phases mean</span>
            <h2>Every plan is a slice of the roadmap</h2>
            <p>
              Early access covers phase 1. Member reaches phase 4, through the underwriting and
              analytics layer. Professional opens all seven, including the AI agent and everything
              that ships after it.
            </p>
          </div>
        </div>
        <div className="wrap">
          <div className="roadmap-scroll">
            {roadmap.map((r) => (
              <div className={`rm-card${r.now ? ' now' : ''}`} key={r.n}>
                <div className="rm-num">P{r.n}</div>
                <h4>{r.title}</h4>
                <p>{r.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="cta-band">
        <div className="wrap">
          <h2>Start on early access — it costs nothing</h2>
          <p>Sign in with Google or Apple, agree to the terms, and pick your plan.</p>
          <div className="hero-ctas">
            <button className="btn btn-primary btn-xl" onClick={signIn}>Get started free</button>
          </div>
        </div>
      </section>
    </PublicPage>
  )
}
