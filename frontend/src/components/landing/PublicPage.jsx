import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { BrandMark } from '../icons/Icons'
import { scrollTo } from '../../lib/scroll'

/** The home page sections the footer links to. The nav stays at Home and
    Pricing — the two destinations, rather than a table of contents. */
const FOOT_SECTIONS = {
  Platform: [
    { id: 'features', label: 'Features' },
    { id: 'use-cases', label: 'Use cases' },
    { id: 'user-types', label: 'Who it is for' },
    { id: 'trust', label: 'Trust & security' },
  ],
  Company: [
    { id: 'about', label: 'About us' },
    { id: 'how-it-works', label: 'How it works' },
    { id: 'roadmap', label: 'Roadmap' },
    { id: 'faq', label: 'FAQs' },
  ],
}

/**
 * The chrome around every page an anonymous visitor sees: the top navigation,
 * the footer, and the body class that lets the window scroll (see landing.css).
 *
 * There are four public pages — Home, the marketing page at `/`, Pricing, the
 * plan list at `/pricing`, and the two legal documents. Get started goes to
 * Pricing: choosing a plan is the first thing a new member does, and sign-in
 * happens on the way.
 */
export default function PublicPage({ page, onLogin, children }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  // Let the page scroll while a public page is up — see landing.css.
  useEffect(() => {
    document.body.classList.add('page-scrolls')
    return () => document.body.classList.remove('page-scrolls')
  }, [])

  /**
   * Routing a link without reloading the page. Every nav and footer link keeps
   * a real `href` so it is focusable, openable in a new tab and readable in the
   * status bar — this is only what happens on a plain left click.
   */
  const route = (to, action) => (e) => {
    e.preventDefault()
    action ? action() : navigate(to)
  }

  /** Going to the page you are already on means going back to the top of it. */
  const go = (to) => route(to, pathname === to ? () => scrollTo('top') : null)

  /** Sections live on the home page; from anywhere else, go there first — the
      hash is what Landing reads to scroll once it has mounted. */
  const goSection = (id) =>
    route(`/#${id}`, page === 'home' ? () => scrollTo(id) : null)

  return (
    <div className="landing" id="top">
      <header className="site-nav">
        <div className="nav-row">
          <div className="brand" onClick={go('/')}>
            <BrandMark style={{ width: 30, height: 30 }} />
            <span className="brand-name">Deal Network</span>
          </div>

          <nav className="nav-links">
            <a href="/" className={page === 'home' ? 'on' : undefined} onClick={go('/')}>Home</a>
            <a
              href="/pricing"
              className={page === 'pricing' ? 'on' : undefined}
              onClick={go('/pricing')}
            >
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
        <div className="wrap">
          <div className="foot-top">
            <div className="foot-brand">
              <div className="brand">
                <BrandMark style={{ width: 24, height: 24 }} />
                <span className="brand-name">Deal Network</span>
              </div>
              <p>
                Networking, CRM, data rooms and underwriting for the people who put property
                deals together.
              </p>
              <button className="btn btn-primary" onClick={go('/pricing')}>Get started free</button>
            </div>

            <div className="foot-cols">
              {Object.entries(FOOT_SECTIONS).map(([heading, links]) => (
                <div className="foot-col" key={heading}>
                  <h4>{heading}</h4>
                  {links.map((l) => (
                    <a href={`/#${l.id}`} key={l.id} onClick={goSection(l.id)}>{l.label}</a>
                  ))}
                </div>
              ))}

              <div className="foot-col">
                <h4>Account</h4>
                <a href="/pricing" onClick={go('/pricing')}>Pricing</a>
                <a href="/login" onClick={route('/login', onLogin)}>Log in</a>
                <a href="/pricing" onClick={go('/pricing')}>Create an account</a>
              </div>

              <div className="foot-col">
                <h4>Legal</h4>
                <a
                  href="/terms"
                  className={pathname === '/terms' ? 'on' : undefined}
                  onClick={go('/terms')}
                >
                  Terms &amp; Conditions
                </a>
                <a
                  href="/privacy"
                  className={pathname === '/privacy' ? 'on' : undefined}
                  onClick={go('/privacy')}
                >
                  Privacy Policy
                </a>
              </div>
            </div>
          </div>

          <div className="foot-row">
            <div className="foot-copy">© {new Date().getFullYear()} Deal Network</div>
            <div className="foot-copy">Early access · Invitation and referral only</div>
          </div>
        </div>
      </footer>
    </div>
  )
}
