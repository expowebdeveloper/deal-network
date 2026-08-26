import { useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { BrandMark, FlowIcon, PresenterIcon } from '../icons/Icons'
import NotificationBell from './NotificationBell'
import GlobalSearch from './GlobalSearch'

export default function Topbar({ locked = false, fullScreen = false }) {
  const {
    openFlow, presenterOpen, togglePresenter, signOut,
    termsAccepted, planSelected, onboarded,
  } = useApp()
  const navigate = useNavigate()

  // Only offer the way back once every step is behind them — otherwise the app
  // would just bounce them to whichever one is still outstanding.
  const canEnterApp = termsAccepted && planSelected && onboarded

  if (locked || fullScreen) {
    return (
      <header className="topbar">
        <div
          className="topbar-brand topbar-brand-always"
          onClick={() => canEnterApp && navigate('/')}
          style={{ cursor: canEnterApp ? 'pointer' : 'default' }}
          title={canEnterApp ? 'Go to Home' : undefined}
        >
          <BrandMark style={{ width: 26, height: 26 }} />
          <span>Deal Network</span>
        </div>
        <div className="topbar-sp" />
        {canEnterApp && (
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/')}>
            ← Back to App
          </button>
        )}
        <button className="btn btn-quiet btn-sm" onClick={signOut}>Sign out</button>
      </header>
    )
  }

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <BrandMark style={{ width: 26, height: 26 }} />
        <span>Deal Network</span>
      </div>

      <GlobalSearch />
      <div className="topbar-sp" />

      <button className="btn btn-ghost btn-sm" onClick={openFlow}>
        <FlowIcon style={{ width: 14, height: 14 }} />
        <span className="lbl-wide">How it connects</span>
      </button>

      <NotificationBell />

      <button
        className={`icon-btn${presenterOpen ? ' on' : ''}`}
        title="Presenter notes"
        onClick={togglePresenter}
      >
        <PresenterIcon />
      </button>

      <button className="btn btn-quiet btn-sm signout-btn" onClick={signOut}>
        Sign out
      </button>
    </header>
  )
}
