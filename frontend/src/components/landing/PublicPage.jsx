import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { BrandMark } from '../icons/Icons'
import { scrollTo } from '../../lib/scroll'

/**
 * The chrome around every page an anonymous visitor sees: the top navigation,
 * the footer, and the body class that lets the window scroll (see landing.css).
 *
 * There are two public pages — Home, the marketing page at `/`, and Pricing, the
 * plan list at `/pricing`. Get started goes to Pricing: choosing a plan is the
 * first thing a new member does, and sign-in happens on the way.
 */
export default function PublicPage({ page, onLogin, children }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { openModal } = useApp()

  // Let the page scroll while a public page is up — see landing.css.
  useEffect(() => {
    document.body.classList.add('page-scrolls')
    return () => document.body.classList.remove('page-scrolls')
  }, [])

  /** Going to the page you are already on means going back to the top of it. */
  const go = (to) => () => (pathname === to ? scrollTo('top') : navigate(to))

  const showTerms = () => openModal('terms')

  return (
    <div className="landing" id="top">
      <header className="site-nav">
        <div className="nav-row">
          <div className="brand" onClick={go('/')}>
            <BrandMark style={{ width: 30, height: 30 }} />
            <span className="brand-name">Deal Network</span>
          </div>

          <nav className="nav-links">
            <a className={page === 'home' ? 'on' : undefined} onClick={go('/')}>Home</a>
            <a className={page === 'pricing' ? 'on' : undefined} onClick={go('/pricing')}>
              Pricing
            </a>
          </nav>

          <div className="nav-actions">
            <button className="btn btn-ghost" onClick={onLogin}>Log in</button>
            <button className="btn btn-primary" onClick={go('/pricing')}>Get started</button>
          </div>
        </div>
      </header>

      {children}

      <footer className="site-foot">
        <div className="wrap foot-row">
          <div className="brand">
            <BrandMark style={{ width: 24, height: 24 }} />
            <span className="brand-name">Deal Network</span>
          </div>
          <div className="foot-links">
            <a onClick={showTerms}>Terms of Use</a>
            <a onClick={showTerms}>Privacy Policy</a>
            <a onClick={go('/')}>Home</a>
            <a onClick={go('/pricing')}>Pricing</a>
            <a onClick={onLogin}>Log in</a>
          </div>
          <div className="foot-copy">Early access · Invitation and referral only</div>
        </div>
      </footer>
    </div>
  )
}
