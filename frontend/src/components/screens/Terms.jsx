import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loading, ErrorState } from '../ui/States'
import { useApp } from '../../context/AppContext'
import { fetchTerms, acceptTerms } from '../../lib/user'
import { termsChecks } from '../../data/onboarding'

/** Renders the mixed plain/bold/muted runs used in the consent labels. */
function Label({ parts }) {
  return parts.map((part, i) => {
    if (typeof part === 'string') return <span key={i}>{part}</span>
    if (part.b) return <b key={i}>{part.b}</b>
    return <span key={i} style={{ color: 'var(--muted)' }}>{part.muted}</span>
  })
}

/**
 * The consent step between signing in and choosing a plan.
 *
 * A route rather than a modal: it cannot be dismissed by clicking away or
 * pressing Escape, and the API enforces the same gate (see require_terms_accepted),
 * so there is nothing behind it to reach anyway.
 *
 * The text and its version come from GET /api/terms — an acceptance is recorded
 * against the version the member was actually shown.
 */
export default function Terms() {
  const { loadSession, signOut } = useApp()
  const navigate = useNavigate()

  const [state, setState] = useState({ status: 'loading', doc: null, error: null })
  const [checked, setChecked] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setState((s) => ({ ...s, status: 'loading' }))
    try {
      setState({ status: 'ready', doc: await fetchTerms(), error: null })
    } catch (err) {
      setState({ status: 'error', doc: null, error: err })
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Continue stays disabled until both required boxes are ticked. The optional
  // marketing one never blocks.
  const required = termsChecks.filter((c) => !c.optional)
  const ready = required.every((c) => checked[c.id])

  async function submit() {
    if (!ready || saving) return
    setSaving(true)
    setError(null)
    try {
      await acceptTerms({
        version: state.doc.version,
        marketingOptIn: !!checked.updates,
      })
      // Re-read /api/me so the gate opens, then on to the plan step.
      await loadSession()
      navigate('/plans', { replace: true })
    } catch (err) {
      // The wording changed while this tab sat open — show the new text.
      if (err.status === 409) {
        setError('These terms have been updated. Please read them again.')
        setChecked({})
        await load()
      } else {
        setError(err.message)
      }
      setSaving(false)
    }
  }

  return (
    /* Same shell as a modal, but no dismiss handler on the backdrop. */
    <div className="modal-back">
      <div className="modal">
        <div className="modal-head">
          <div className="tt">
            <h2>Before you continue</h2>
            <p>Plain-language summary of what you are agreeing to.</p>
          </div>
        </div>

        <div className="modal-body">
          {error && <div className="inline-error">{error}</div>}

          {state.status === 'loading' && <Loading label="Loading the terms…" />}
          {state.status === 'error' && <ErrorState error={state.error} onRetry={load} />}

          {state.status === 'ready' && (
            <>
              <div className="card terms-box">
                <div className="terms-text">
                  {state.doc.sections.map((s, i) => (
                    <span key={s.heading}>
                      <b>{s.heading}</b> {s.body}
                      {i < state.doc.sections.length - 1 && <><br /><br /></>}
                    </span>
                  ))}
                </div>
              </div>

              {termsChecks.map((c) => (
                <label className="terms-check" key={c.id}>
                  <input
                    type="checkbox"
                    checked={!!checked[c.id]}
                    onChange={(e) =>
                      setChecked((v) => ({ ...v, [c.id]: e.target.checked }))
                    }
                  />
                  <span><Label parts={c.text} /></span>
                </label>
              ))}
            </>
          )}
        </div>

        <div className="modal-foot">
          {/* There is no screen behind this one, so Back means sign out. */}
          <button className="btn btn-ghost" onClick={signOut} disabled={saving}>
            Back
          </button>
          <button
            className="btn btn-primary"
            onClick={submit}
            disabled={!ready || saving}
            data-busy={saving}
          >
            {saving ? 'Saving…' : 'Continue'}
          </button>
        </div>
      </div>
    </div>
  )
}
