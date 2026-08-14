import { useEffect, useState } from 'react'
import Modal from '../ui/Modal'
import { useApp } from '../../context/AppContext'
import { BrandMark, GoogleIcon, AppleIcon, CloseIcon } from '../icons/Icons'
import { fetchProviders, startOAuth } from '../../lib/api'
import { loginStats } from '../../data/user'

/** Messages the backend can hand back on /auth/callback#error=… */
const ERROR_COPY = {
  access_denied: 'You cancelled the sign-in. Try again when you are ready.',
  missing_code: 'The provider did not return an authorization code. Please try again.',
  oauth_exchange_failed:
    'We could not complete sign-in with that provider. Check the server credentials and try again.',
  user_cancelled_authorize: 'You cancelled the sign-in. Try again when you are ready.',
  session_failed: 'Signed in, but we could not load your profile. Please try again.',
}

function describeError(code) {
  if (!code) return null
  if (ERROR_COPY[code]) return ERROR_COPY[code]
  if (code.startsWith('invalid_state')) return 'That sign-in link expired. Please start again.'
  return `Sign-in failed (${code}).`
}

/**
 * Sign in, as a dialog over the landing page.
 *
 * `error` is the code the OAuth callback bounced back with — /login?error=… is
 * where a failed round trip lands, and the landing page opens this with it.
 */
export default function LoginModal({ error = null, onClose }) {
  const { closeModal, openModal } = useApp()

  // null = we do not know which providers exist — either still checking, or the
  // lookup failed. Never [] on failure: an empty list reads as "the server has
  // no providers configured", which is a different problem with a different fix.
  const [providers, setProviders] = useState(null)
  const [checking, setChecking] = useState(true)
  const [problem, setProblem] = useState(() => describeError(error))
  const [busy, setBusy] = useState(null)

  // Ask the backend which providers it can actually service.
  useEffect(() => {
    let cancelled = false
    fetchProviders()
      .then((data) => {
        if (!cancelled) setProviders(data.providers.map((p) => p.name))
      })
      .catch((err) => {
        if (cancelled) return
        setProblem(
          err.status === 0
            ? 'Cannot reach the API. Start the backend with: uvicorn app.main:app --reload — ' +
              'if it is running, check that this page’s address is listed in CORS_ORIGINS ' +
              'in backend/.env.'
            : 'Could not load sign-in options from the server. Signing in may still work.',
        )
      })
      .finally(() => { if (!cancelled) setChecking(false) })
    return () => { cancelled = true }
  }, [])

  function handleSignIn(provider) {
    if (busy) return
    if (providers && !providers.includes(provider)) {
      setProblem(
        provider === 'google'
          ? 'Google sign-in is not configured on the server yet. Add GOOGLE_CLIENT_ID and ' +
            'GOOGLE_CLIENT_SECRET to backend/.env and restart the API.'
          : 'Apple sign-in is not configured on the server yet. Add the APPLE_* values to ' +
            'backend/.env and restart the API.',
      )
      return
    }
    setBusy(provider)
    setProblem(null)
    startOAuth(provider) // full-page redirect to the backend, then on to the provider
  }

  function close() {
    onClose?.()
    closeModal()
  }

  function showTerms(e) {
    e.preventDefault()
    // Single modal slot — offer the way back to this one.
    openModal('terms', { onBack: () => openModal('login', { onClose }) })
  }

  return (
    <Modal className="login-modal">
      <div className="login-split">
        {/* The pitch. Hidden on small screens, where the dialog is a sheet. */}
        <aside className="login-aside">
          <div className="login-glow" />
          <div className="brand">
            <BrandMark />
            <span className="brand-name">Deal Network</span>
          </div>

          <div className="login-pitch">
            <h1>Where property people actually find each other.</h1>
            <p>
              Profiles, communities and contact management built for developers, investors,
              brokers and lenders — organised by the regions and asset classes you actually
              work in.
            </p>
            <div className="login-stats">
              {loginStats.map((s) => (
                <div className="login-stat" key={s.l}>
                  <div className="n">{s.n}</div>
                  <div className="l">{s.l}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="login-foot">Early access · Invitation and referral only</div>
        </aside>

        <div className="login-pane">
          <button className="modal-close" onClick={close} aria-label="Close">
            <CloseIcon />
          </button>

          <div className="login-form">
            <h2>Sign in</h2>
            <p className="sub">Use the account you already work from.</p>

            {problem && <div className="login-alert" role="alert">{problem}</div>}

            <button
              className="oauth"
              onClick={() => handleSignIn('google')}
              disabled={checking || busy !== null}
            >
              <GoogleIcon />
              {busy === 'google' ? 'Redirecting to Google…' : 'Continue with Google'}
            </button>

            <button
              className="oauth oauth-apple"
              onClick={() => handleSignIn('apple')}
              disabled={checking || busy !== null}
            >
              <AppleIcon />
              {busy === 'apple' ? 'Redirecting to Apple…' : 'Continue with Apple'}
            </button>

            <div className="login-or">SECURE SIGN-IN</div>

            <p className="login-legal">
              By continuing you agree to our <a href="#terms" onClick={showTerms}>Terms of Use</a>{' '}
              and <a href="#privacy" onClick={showTerms}>Privacy Policy</a>, including how your
              company and deal information is stored and retained.
            </p>
          </div>
        </div>
      </div>
    </Modal>
  )
}
