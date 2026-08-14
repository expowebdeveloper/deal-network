import { Routes, Route, Navigate } from 'react-router-dom'
import { useApp } from './context/AppContext'
import AppShell from './components/layout/AppShell'
import Landing from './components/landing/Landing'
import Pricing from './components/landing/Pricing'
import AuthCallback from './components/login/AuthCallback'
import Home from './components/screens/Home'
import Communities from './components/screens/Communities'
import Members from './components/screens/Members'
import Investors from './components/screens/Investors'
import Contacts from './components/screens/Contacts'
import Plans from './components/screens/Plans'
import Terms from './components/screens/Terms'
import Onboarding from './components/screens/Onboarding'
import Profile from './components/screens/Profile'
import ModalHost from './components/modals/ModalHost'
import FlowView from './components/flow/FlowView'
import Presenter from './components/presenter/Presenter'
import { BrandMark } from './components/icons/Icons'

/** Shown while a stored token is being replayed against /api/me. */
function Booting() {
  return (
    <div className="auth-callback">
      <BrandMark />
      <p>Loading…</p>
    </div>
  )
}

export default function App() {
  const { signedIn, termsAccepted, planSelected, onboarded, authState, flowOpen } = useApp()

  return (
    <>
      <Routes>
        {/* The OAuth landing spot must resolve before the auth check below. */}
        <Route path="/auth/callback" element={<AuthCallback />} />

        {authState === 'loading' ? (
          <Route path="*" element={<Booting />} />
        ) : !signedIn ? (
          /* Anonymous: the marketing page is the front door. Signing in is a
             dialog over it, and /login is the URL that opens that dialog. */
          <>
            <Route index element={<Landing />} />
            <Route path="login" element={<Landing />} />
            <Route path="pricing" element={<Pricing />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </>
        ) : !termsAccepted ? (
          /* Signed in but the terms are not agreed to — the first gate. */
          <Route element={<AppShell locked />}>
            <Route path="terms" element={<Terms />} />
            <Route path="*" element={<Navigate to="/terms" replace />} />
          </Route>
        ) : !planSelected ? (
          /* Terms agreed to but no plan chosen — the only screen available is Plans in fullscreen. */
          <Route element={<AppShell locked />}>
            <Route path="plans" element={<Plans onboarding />} />
            <Route path="*" element={<Navigate to="/plans" replace />} />
          </Route>
        ) : !onboarded ? (
          /* Plan chosen — the last step is setting the profile up. Plans stays
             reachable so Back on step 1 has somewhere to go. */
          <Route element={<AppShell locked />}>
            <Route path="onboarding" element={<Onboarding />} />
            <Route path="plans" element={<Plans />} />
            <Route path="*" element={<Navigate to="/onboarding" replace />} />
          </Route>
        ) : (
          <>
            {/* The public pricing page is the signed-in plans screen. */}
            <Route path="pricing" element={<Navigate to="/plans" replace />} />

            {/* The plans page is displayed full screen (hiding the sidebar) */}
            <Route element={<AppShell fullScreen />}>
              <Route path="plans" element={<Plans />} />
            </Route>

            {/* Main application screens with the full sidebar visible */}
            <Route element={<AppShell />}>
              <Route index element={<Home />} />
              <Route path="communities" element={<Communities />} />
              <Route path="members" element={<Members />} />
              <Route path="investors" element={<Investors />} />
              <Route path="contacts" element={<Contacts />} />
              <Route path="profile" element={<Profile />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </>
        )}
      </Routes>

      {/* Overlays live outside the shell so they can cover it. */}
      {signedIn && planSelected && <Presenter />}
      {signedIn && planSelected && flowOpen && <FlowView />}
      <ModalHost />
    </>
  )
}
