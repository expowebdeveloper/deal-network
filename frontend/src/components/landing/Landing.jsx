import { useCallback, useEffect } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { ArrowRightIcon } from '../icons/Icons'
import PublicPage from './PublicPage'
import { scrollTo } from '../../lib/scroll'
import { ICONS } from './moduleIcons'
import { heroStats, benefits, modules, roadmap } from '../../data/landing'

/**
 * The public landing page — what an anonymous visitor sees at `/`.
 *
 * Log in opens the sign-in dialog over it (see LoginModal); /login is the URL
 * that dialog lives at, so it can be linked to and bookmarked. Get started goes
 * to the plans instead — see PublicPage.
 */
export default function Landing() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [params] = useSearchParams()
  const { openModal } = useApp()

  /** Sign-in is a dialog over this page; /login is the URL that opens it. */
  const goToLogin = useCallback(
    (error = null) => {
      if (pathname !== '/login') navigate('/login')
      openModal('login', { error, onClose: () => navigate('/', { replace: true }) })
    },
    [navigate, openModal, pathname],
  )

  // Landing straight on /login — a bookmark, or the OAuth callback bouncing an
  // error back — opens the dialog with nothing else to click through first.
  useEffect(() => {
    if (pathname === '/login') goToLogin(params.get('error'))
    // Only on arrival: reopening on every render would fight the close button.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname])

  return (
    <PublicPage page="home" onLogin={() => goToLogin()}>
      <section className="hero">
        <div className="wrap hero-inner">
          <span className="eyebrow">For developers, investors, brokers &amp; lenders</span>
          <h1>Where property people actually find each other — and get the deal done.</h1>
          <p className="sub">
            Networking, CRM, data rooms and underwriting in one platform, organised around the
            markets and asset classes you actually work in. Stop juggling six tools to run one deal.
          </p>
          <div className="hero-ctas">
            <button className="btn btn-primary btn-xl" onClick={() => navigate('/pricing')}>
              Get started
            </button>
            <button className="btn btn-on-dark btn-xl" onClick={() => scrollTo('features')}>
              See what&apos;s inside
            </button>
          </div>
          <div className="hero-stats">
            {heroStats.map((s) => (
              <div className="hero-stat" key={s.l}>
                <div className="n">{s.n}</div>
                <div className="l">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="strip">
        <div className="strip-row">
          {benefits.map((b) => {
            const Icon = ICONS[b.icon]
            return (
              <div className="strip-item" key={b.n}>
                <Icon />
                <div>
                  <div className="n">{b.n}</div>
                  <div className="l">{b.l}</div>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section className="landing-section" id="features">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">Everything in one place</span>
            <h2>Every module you&apos;d otherwise stitch together yourself</h2>
            <p>
              Click any module to see exactly what&apos;s included. Deal Network ships this in
              phases — each card shows where it lands on the roadmap.
            </p>
          </div>

          <div className="feat-grid">
            {modules.map((m) => {
              const Icon = ICONS[m.icon]
              return (
                <button
                  className="card feat-card"
                  key={m.id}
                  onClick={() => openModal('feature', { moduleId: m.id })}
                >
                  <div className="feat-top">
                    <div className={`feat-avatar ${m.avatar}`}><Icon /></div>
                    {m.pro
                      ? <span className="tag tag-gold">Pro feature</span>
                      : <span className="chip">{m.phase}</span>}
                  </div>
                  <div>
                    <h3>{m.title}</h3>
                    <p>{m.blurb}</p>
                  </div>
                  <div className="feat-foot">
                    {m.pro ? <span className="chip">{m.phase}</span> : <span />}
                    <span className="feat-more">View details <ArrowRightIcon /></span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </section>

      <section className="roadmap" id="roadmap">
        <div className="wrap roadmap-head">
          <div className="section-head">
            <span className="eyebrow">Built in phases</span>
            <h2>How Deal Network gets built out</h2>
            <p>
              We ship a working platform first, then layer on data rooms, analytics and AI — not
              the other way around.
            </p>
          </div>
        </div>
        <div className="wrap">
          <div className="roadmap-scroll">
            {roadmap.map((r) => (
              <div className={`rm-card${r.now ? ' now' : ''}`} key={r.n}>
                <div className="rm-num">P{r.n}</div>
                <h4>{r.title}</h4>
                <p>{r.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="cta-band">
        <div className="wrap">
          <h2>Ready to see it running?</h2>
          <p>Pick a plan and sign in with Google or Apple — early access is free, no card.</p>
          <div className="hero-ctas">
            <button className="btn btn-primary btn-xl" onClick={() => navigate('/pricing')}>
              Get started free
            </button>
          </div>
        </div>
      </section>
    </PublicPage>
  )
}
