import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Field, { FieldRow } from '../ui/Field'
import Chip from '../ui/Chip'
import Avatar from '../ui/Avatar'
import { Loading, ErrorState } from '../ui/States'
import { useApp } from '../../context/AppContext'
import { fetchOnboarding, chooseRole, completeProfileSetup } from '../../lib/user'

/** The progress dashes above the wizard. */
function Steps({ step, total }) {
  return (
    <div className="steps">
      {Array.from({ length: total }, (_, i) => (
        <div key={i} className={`step${i < step ? ' on' : ''}`} />
      ))}
    </div>
  )
}

/**
 * Profile setup: the step between choosing a plan and the app.
 *
 * Two screens — the role picker, then company details — driven by
 * GET /api/onboarding, which also says which step the member is on. Each step
 * saves as it is finished, so a reload resumes rather than restarts.
 *
 * A route rather than a modal, for the same reason as the terms gate: it cannot
 * be clicked away, and the app behind it is not ready for them yet.
 */
export default function Onboarding() {
  const { loadSession, user } = useApp()
  const navigate = useNavigate()

  const [state, setState] = useState({ status: 'loading', data: null, error: null })
  const [role, setRole] = useState(null)
  const [form, setForm] = useState({
    company: '', primary_market: '', team_size: '', short_description: '',
  })
  const [assets, setAssets] = useState(() => new Set())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setState((s) => ({ ...s, status: 'loading' }))
    try {
      const data = await fetchOnboarding()
      setState({ status: 'ready', data, error: null })
      setRole(data.role)
      setAssets(new Set(data.asset_classes))
      setForm({
        // Fall back to what the profile already knows, so a member who filled
        // any of this in elsewhere does not retype it.
        company: data.company ?? user?.company ?? '',
        primary_market: data.primary_market ?? data.options.markets[0],
        team_size: data.team_size ?? data.options.team_sizes[0],
        short_description: data.short_description ?? '',
      })
    } catch (err) {
      setState({ status: 'error', data: null, error: err })
    }
  }, [user])

  useEffect(() => { load() }, [load])

  const data = state.data
  const step = data?.step ?? 1
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  function toggleAsset(label) {
    setAssets((cur) => {
      const next = new Set(cur)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }

  async function submitRole() {
    if (!role || saving) return
    setSaving(true)
    setError(null)
    try {
      const next = await chooseRole(role)
      setState((s) => ({ ...s, data: { ...next, options: next.options } }))
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function finish() {
    if (saving) return
    if (!form.company.trim()) {
      setError('Add your company name.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await completeProfileSetup({
        company: form.company.trim(),
        primary_market: form.primary_market,
        team_size: form.team_size,
        asset_classes: [...assets],
        short_description: form.short_description.trim() || null,
      })
      // Re-read /api/me so the gate opens, then show them what they just built.
      await loadSession()
      navigate('/profile', { replace: true })
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  /** Step 1 sends them back to the plan step; step 2 back to the role picker. */
  function back() {
    if (step === 1) navigate('/plans')
    else setState((s) => ({ ...s, data: { ...s.data, step: 1 } }))
  }

  return (
    /* Same shell as a modal, but no dismiss handler on the backdrop. */
    <div className="modal-back">
      <div className="modal">
        {state.status !== 'ready' ? (
          <div className="modal-body">
            {state.status === 'loading' && <Loading label="Loading your setup…" />}
            {state.status === 'error' && <ErrorState error={state.error} onRetry={load} />}
          </div>
        ) : step === 1 ? (
          <>
            <div className="modal-head">
              <div className="tt">
                <h2>What describes you best?</h2>
                <p>
                  This sets which communities and members we suggest first. You can change
                  it later.
                </p>
              </div>
            </div>

            <div className="modal-body">
              {error && <div className="inline-error">{error}</div>}
              {data.options.roles.map((option, i) => (
                <button
                  key={option.id}
                  className={`card role-opt${role === option.id ? ' on' : ''}`}
                  onClick={() => setRole(option.id)}
                >
                  <Avatar initials={i + 1} color={`a${i + 1}`} size="sm" />
                  <div style={{ flex: 1 }}>
                    <div className="t">{option.title}</div>
                    <div className="d">{option.description}</div>
                  </div>
                  <div className="radio" />
                </button>
              ))}
            </div>

            <div className="modal-foot">
              <button className="btn btn-ghost" onClick={back} disabled={saving}>Back</button>
              <button
                className="btn btn-primary"
                onClick={submitRole}
                disabled={!role || saving}
                data-busy={saving}
              >
                {saving ? 'Saving…' : 'Continue'}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="modal-head">
              <div className="tt">
                <h2>Set up your profile</h2>
                <p>Step {step} of {data.total_steps} · Company details</p>
                <Steps step={step} total={data.total_steps} />
              </div>
            </div>

            <div className="modal-body">
              {error && <div className="inline-error">{error}</div>}

              <Field label="Company name">
                <input
                  value={form.company}
                  onChange={set('company')}
                  placeholder="The company other members will see"
                  autoFocus
                />
              </Field>

              <FieldRow>
                <Field label="Primary market">
                  <select value={form.primary_market} onChange={set('primary_market')}>
                    {data.options.markets.map((m) => <option key={m}>{m}</option>)}
                  </select>
                </Field>
                <Field label="Team size">
                  <select value={form.team_size} onChange={set('team_size')}>
                    {data.options.team_sizes.map((t) => <option key={t}>{t}</option>)}
                  </select>
                </Field>
              </FieldRow>

              <Field label="Asset classes you work in">
                <div className="chip-wrap">
                  {data.options.asset_classes.map((label) => (
                    <Chip key={label} on={assets.has(label)} onClick={() => toggleAsset(label)}>
                      {label}
                    </Chip>
                  ))}
                </div>
              </Field>

              <Field label="Short description" className="last-field">
                <textarea
                  value={form.short_description}
                  onChange={set('short_description')}
                  placeholder="One or two lines other members will see on your profile."
                />
              </Field>
            </div>

            <div className="modal-foot">
              <button className="btn btn-ghost" onClick={back} disabled={saving}>Back</button>
              <button
                className="btn btn-primary"
                onClick={finish}
                disabled={saving}
                data-busy={saving}
              >
                {saving ? 'Saving…' : 'Finish setup'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
