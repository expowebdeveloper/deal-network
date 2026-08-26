import { useCallback, useEffect } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { ArrowRightIcon, ArrowDownIcon, CheckIcon } from '../icons/Icons'
import PublicPage from './PublicPage'
import { scrollTo } from '../../lib/scroll'
import { ICONS } from './moduleIcons'
import {
  heroStats, benefits, roadmap, steps, whyUs, useCases, userTypes,
  testimonials, trust, about, faqs,
} from '../../data/landing'
import { phases, phaseItemCount } from '../../data/phases'

/**
 * The public landing page — what an anonymous visitor sees at `/`.
 *
 * Log in opens the sign-in dialog over it (see LoginModal); /login is the URL
 * that dialog lives at, so it can be linked to and bookmarked. Get started goes
 * to the plans instead — see PublicPage.
 */
/** Icon tile used by every section that leads a card with an icon. */
function Tile({ icon, className = 'a1' }) {
  const Icon = ICONS[icon]
  return <div className={`feat-avatar ${className}`}><Icon /></div>
}

export default function Landing() {
  const navigate = useNavigate()
  const { pathname, hash } = useLocation()
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

  // The page is long enough that its sections are worth linking to. `/#faq` is
  // what the nav and footer use to reach one from another public page.
  useEffect(() => {
    if (hash) scrollTo(hash.slice(1))
  }, [hash])

  /** In-page links to the legal documents, routed rather than reloaded. */
  const goTo = (to) => (e) => {
    e.preventDefault()
    navigate(to)
  }

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

      <section className="landing-section tint" id="how-it-works">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">How it works</span>
            <h2>From signing up to signing off, in four steps</h2>
            <p>
              No implementation project and no data migration. You are in a community the day
              you join, and the deal tools switch on as you need them.
            </p>
          </div>

          <ol className="how-grid">
            {steps.map((s) => (
              <li className="card how-card" key={s.n}>
                <div className="how-top">
                  <Tile icon={s.icon} className={`a${s.n}`} />
                  <span className="how-num">{String(s.n).padStart(2, '0')}</span>
                </div>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="landing-section" id="features">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">The build plan</span>
            <h2>Seven phases, and exactly what is in each one</h2>
            <p>
              Click any phase to see the full feature list behind it — every item, its group and
              where it currently stands.
            </p>
          </div>

          <div className="feat-grid">
            {phases.map((p) => (
              <button
                className="card feat-card"
                key={p.n}
                onClick={() => openModal('phase', { phaseNumber: p.n })}
              >
                <div className="feat-top">
                  <Tile icon={p.icon} className={p.avatar} />
                  <span className="chip">Phase {p.n}</span>
                </div>
                <div>
                  <h3>{p.name}</h3>
                  <p>{p.blurb}</p>
                </div>
                <div className="feat-foot">
                  <span className="feat-count">{phaseItemCount(p)} features</span>
                  <span className="feat-more">View details <ArrowRightIcon /></span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-section tint" id="why-us">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">Why choose us</span>
            <h2>Why property people move over</h2>
            <p>
              Generic sales software was never built for a deal that runs eighteen months and
              involves nine parties. This was.
            </p>
          </div>

          <div className="why-grid">
            {whyUs.map((w, i) => (
              <div className="why-card" key={w.title}>
                <Tile icon={w.icon} className={`a${(i % 6) + 1}`} />
                <div>
                  <h3>{w.title}</h3>
                  <p>{w.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-section" id="use-cases">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">Use cases</span>
            <h2>What members open it to do</h2>
            <p>
              Six jobs that currently take four tools and a group chat. Each one is a single
              thread on Deal Network.
            </p>
          </div>

          <div className="uc-grid">
            {useCases.map((u) => {
              const Icon = ICONS[u.icon]
              return (
                <div className="card uc-card" key={u.title}>
                  <span className="uc-icon"><Icon /></span>
                  <div>
                    <h3>{u.title}</h3>
                    <p>{u.desc}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      <section className="landing-section tint" id="user-types">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">Who it is for</span>
            <h2>Five sides of the same deal</h2>
            <p>
              A network only works when every side of the table is on it. You pick your role when
              you join, and the platform shapes itself around it.
            </p>
          </div>

          <div className="ut-grid">
            {userTypes.map((t, i) => (
              <div className="card ut-card" key={t.title}>
                <Tile icon={t.icon} className={`a${i + 1}`} />
                <h3>{t.title}</h3>
                <p className="ut-desc">{t.desc}</p>
                <ul>
                  {t.points.map((p) => (
                    <li key={p}><CheckIcon />{p}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-section" id="testimonials">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">Testimonials</span>
            <h2>What early members tell us</h2>
            <p>Shared anonymously, by role — early access members are not published by name.</p>
          </div>

          <div className="quote-grid">
            {testimonials.map((t) => (
              <figure className="card quote-card" key={t.q}>
                <span className="quote-mark" aria-hidden="true">&ldquo;</span>
                <blockquote>{t.q}</blockquote>
                <figcaption>
                  <span className={`avatar avatar-sm ${t.color}`}>{t.initials}</span>
                  <span>
                    <span className="quote-who">{t.who}</span>
                    <span className="quote-org">{t.org}</span>
                  </span>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <section className="trust" id="trust">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">Trust &amp; security</span>
            <h2>Deal information is the most sensitive thing you own</h2>
            <p>
              So it is handled that way — permissioned, encrypted, expiring, and never used to
              train anything of ours.
            </p>
          </div>

          <div className="trust-grid">
            {trust.map((t) => {
              const Icon = ICONS[t.icon]
              return (
                <div className="trust-item" key={t.title}>
                  <Icon />
                  <div>
                    <h3>{t.title}</h3>
                    <p>{t.desc}</p>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="trust-stats">
            {heroStats.map((s) => (
              <div className="hero-stat" key={s.l}>
                <div className="n">{s.n}</div>
                <div className="l">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="roadmap" id="roadmap">
        <div className="wrap roadmap-head">
          <div className="section-head">
            <span className="eyebrow">Coming soon · built in phases</span>
            <h2>What is live, and what lands next</h2>
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

      <section className="landing-section" id="about">
        <div className="wrap about-grid">
          <div className="about-copy">
            <span className="eyebrow">About us</span>
            <h2>{about.title}</h2>
            {about.body.map((para) => <p key={para}>{para}</p>)}
          </div>
          <aside className="card about-points">
            {about.points.map((p) => (
              <div className="about-point" key={p.n}>
                <div className="n">{p.n}</div>
                <div className="l">{p.l}</div>
              </div>
            ))}
            <button className="btn btn-ghost btn-block" onClick={() => scrollTo('roadmap')}>
              See the full roadmap
            </button>
          </aside>
        </div>
      </section>

      <section className="landing-section tint" id="faq">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">FAQs</span>
            <h2>Questions we get asked before people sign up</h2>
            <p>
              Anything not covered here, ask us once you are in — or read the{' '}
              <a className="link" href="/terms" onClick={goTo('/terms')}>Terms</a> and{' '}
              <a className="link" href="/privacy" onClick={goTo('/privacy')}>Privacy Policy</a>{' '}
              in full.
            </p>
          </div>

          <div className="faq-list">
            {faqs.map((f) => (
              <details className="faq-item" key={f.q}>
                <summary>
                  <span>{f.q}</span>
                  <ArrowDownIcon />
                </summary>
                <p>{f.a}</p>
              </details>
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
