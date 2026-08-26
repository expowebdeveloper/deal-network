import { Routes, Route, Navigate, useParams } from 'react-router-dom'
import { useApp } from './context/AppContext'
import AppShell from './components/layout/AppShell'
import Landing from './components/landing/Landing'
import Pricing from './components/landing/Pricing'
import Legal from './components/landing/Legal'
import AuthCallback from './components/login/AuthCallback'
import BillingReturn from './components/billing/BillingReturn'
import Home from './components/screens/Home'
import Communities from './components/screens/Communities'
import Members from './components/screens/Members'
import Investors from './components/screens/Investors'
import Contacts from './components/screens/Contacts'
import Plans from './components/screens/Plans'
import Terms from './components/screens/Terms'
import Onboarding from './components/screens/Onboarding'
import Profile from './components/screens/Profile'
import MemberProfile from './components/screens/MemberProfile'
import ModalHost from './components/modals/ModalHost'
import FlowView from './components/flow/FlowView'
import Presenter from './components/presenter/Presenter'
import { BrandMark } from './components/icons/Icons'

/** Redirects /communities/:slug/settings to /communities?settings=:slug */
function CommunitySettingsRedirect() {
  const { slug } = useParams()
  return <Navigate to={`/communities?settings=${slug}`} replace />
}

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
            {/* The public legal documents, linked from the footer. `/terms`
                below is the consent gate a signed-in member has to clear —
                a different screen for a different job. */}
            <Route path="privacy" element={<Legal doc="privacy" />} />
            <Route path="terms" element={<Legal doc="terms" />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </>
        ) : !termsAccepted ? (
          /* Signed in but the terms are not agreed to — the first gate. Stripe's
             return path is listed in every signed-in branch because a member
             comes back from Checkout mid-flow, possibly before a gate has
             opened, and must not be bounced away from the confirmation. */
          <Route element={<AppShell locked />}>
            <Route path="billing/success" element={<BillingReturn />} />
            <Route path="terms" element={<Terms />} />
            <Route path="*" element={<Navigate to="/terms" replace />} />
          </Route>
        ) : !planSelected ? (
          /* Terms agreed to but no plan chosen — the only screen available is Plans in fullscreen. */
          <Route element={<AppShell locked />}>
            <Route path="billing/success" element={<BillingReturn />} />
            <Route path="plans" element={<Plans onboarding />} />
            <Route path="*" element={<Navigate to="/plans" replace />} />
          </Route>
        ) : !onboarded ? (
          /* Plan chosen — the last step is setting the profile up. Plans stays
             reachable so Back on step 1 has somewhere to go. */
          <Route element={<AppShell locked />}>
            <Route path="billing/success" element={<BillingReturn />} />
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
              <Route path="billing/success" element={<BillingReturn />} />
            </Route>

            {/* Main application screens with the full sidebar visible */}
            <Route element={<AppShell />}>
              <Route index element={<Home />} />
              <Route path="communities" element={<Communities />} />
              <Route path="communities/:slug/settings" element={<CommunitySettingsRedirect />} />
              <Route path="members" element={<Members />} />
              {/* Someone else's profile. Distinct from /profile, which is your
                  own and is the only one with Edit and Field visibility. */}
              <Route path="members/:userId" element={<MemberProfile />} />
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
