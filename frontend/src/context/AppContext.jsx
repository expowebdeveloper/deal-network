import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { ApiError, fetchMe, logout, tokens } from '../lib/api'

const AppContext = createContext(null)

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>')
  return ctx
}

/**
 * Holds the state that lives above the screens: the session, the single active
 * modal, the flow overlay and the presenter drawer.
 *
 * Auth is real: tokens come from the backend's OAuth callback and live in
 * sessionStorage (see lib/api.js). On boot we replay them against /api/me, so a
 * refresh or a deep link keeps you signed in and a revoked token signs you out.
 *
 * `modal` is { name, props } — screens call openModal('connect', {...}) and the
 * host in App.jsx decides which component to render.
 */
export function AppProvider({ children }) {
  const [user, setUser] = useState(null)
  // 'loading' until the stored token has been checked, so the login screen
  // does not flash for an already-signed-in member.
  const [authState, setAuthState] = useState(tokens.access ? 'loading' : 'anonymous')

  const [modal, setModal] = useState(null)
  const [flowOpen, setFlowOpen] = useState(false)
  const [presenterOpen, setPresenterOpen] = useState(false)

  const openModal = useCallback((name, props = {}) => setModal({ name, props }), [])
  const closeModal = useCallback(() => setModal(null), [])
  const openFlow = useCallback(() => setFlowOpen(true), [])
  const closeFlow = useCallback(() => setFlowOpen(false), [])
  const togglePresenter = useCallback(() => setPresenterOpen((v) => !v), [])
  const closePresenter = useCallback(() => setPresenterOpen(false), [])

  /** Called by the OAuth callback route once tokens are stored. */
  const loadSession = useCallback(async () => {
    if (!tokens.access) {
      setAuthState('anonymous')
      setUser(null)
      return null
    }
    setAuthState('loading')
    try {
      const me = await fetchMe()
      setUser(me)
      setAuthState('authenticated')
      return me
    } catch (error) {
      // A dead token means signed out; a dead backend should not wipe the session.
      if (error instanceof ApiError && error.status === 401) tokens.clear()
      setUser(null)
      setAuthState('anonymous')
      throw error
    }
  }, [])

  const signOut = useCallback(async () => {
    closeModal()
    closeFlow()
    closePresenter()
    // Drop to the sign-in screen straight away; the revoke call still needs the
    // tokens in storage, and logout() clears them when it is done either way.
    setUser(null)
    setAuthState('anonymous')
    try {
      await logout()
    } catch {
      /* backend unreachable — the session is gone locally regardless */
    }
  }, [closeModal, closeFlow, closePresenter])

  // Replay a stored token on first load.
  useEffect(() => {
    if (!tokens.access) return
    loadSession().catch(() => {})
  }, [loadSession])

  // Escape closes the modal and the flow overlay, as in the prototype.
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key !== 'Escape') return
      closeModal()
      closeFlow()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [closeModal, closeFlow])

  const value = useMemo(
    () => ({
      user, authState,
      signedIn: authState === 'authenticated',
      // Two gates stand between signing in and the app: agree to the terms,
      // then choose a plan. The API enforces both — see require_terms_accepted
      // and require_plan_selected.
      termsAccepted: !!user?.terms_accepted,
      planSelected: !!user?.plan_selected,
      // The last step: profile setup. Recorded server-side on /api/onboarding.
      onboarded: !!user?.onboarded,
      currentPlan: user?.current_plan ?? null,
      loadSession, signOut,
      modal, openModal, closeModal,
      flowOpen, openFlow, closeFlow,
      presenterOpen, togglePresenter, closePresenter,
    }),
    [user, authState, loadSession, signOut, modal, openModal, closeModal,
     flowOpen, openFlow, closeFlow, presenterOpen, togglePresenter, closePresenter],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}
