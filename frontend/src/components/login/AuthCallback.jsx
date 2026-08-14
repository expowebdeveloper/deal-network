import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { BrandMark } from '../icons/Icons'
import { tokens } from '../../lib/api'

/**
 * Landing spot for the backend's OAuth redirect.
 *
 * The backend sends tokens in the URL *fragment* (`#access_token=…`), which the
 * browser never transmits to a server. We read it, store the pair, wipe the hash
 * from history so the tokens do not linger in the address bar, then load /api/me.
 */
export default function AuthCallback() {
  const { loadSession } = useApp()
  const navigate = useNavigate()
  const handled = useRef(false)
  const [message, setMessage] = useState('Finishing sign-in…')

  useEffect(() => {
    if (handled.current) return
    handled.current = true

    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''))
    const error = params.get('error')
    const accessToken = params.get('access_token')
    const refreshToken = params.get('refresh_token')

    // Drop the fragment either way, so tokens are not left in the URL bar.
    window.history.replaceState(null, '', window.location.pathname)

    if (error) {
      navigate(`/login?error=${encodeURIComponent(error)}`, { replace: true })
      return
    }
    if (!accessToken || !refreshToken) {
      navigate('/login?error=missing_code', { replace: true })
      return
    }

    tokens.set({ access_token: accessToken, refresh_token: refreshToken })

    loadSession()
      .then((me) => {
        // Sign-in lands on the first step still outstanding: agree to the terms,
        // choose a plan, set the profile up. Once all three are done it goes
        // straight into the app — otherwise every return visit would open on a
        // page they are done with.
        if (!me?.terms_accepted) navigate('/terms', { replace: true })
        else if (!me.plan_selected) navigate('/plans', { replace: true })
        else navigate(me.onboarded ? '/' : '/onboarding', { replace: true })
      })
      .catch(() => {
        setMessage('Could not load your profile.')
        navigate('/login?error=session_failed', { replace: true })
      })
  }, [loadSession, navigate])

  return (
    <div className="auth-callback">
      <BrandMark />
      <p>{message}</p>
    </div>
  )
}
