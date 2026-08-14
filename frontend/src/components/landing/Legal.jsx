import { useEffect } from 'react'
import { useApp } from '../../context/AppContext'
import PublicPage from './PublicPage'
import { legalDocs, legalMeta } from '../../data/legal'

/**
 * The public legal documents — the Privacy Policy at `/privacy` and the Terms &
 * Conditions at `/terms`, both linked from the footer of every public page.
 *
 * These are the long-form documents anyone can read before signing up. The
 * short consent summary a new member ticks through on the way in is a different
 * screen — see TermsModal and screens/Terms.jsx.
 */
export default function Legal({ doc }) {
  const { openModal } = useApp()
  const content = legalDocs[doc]

  // Arriving here from a footer link halfway down a long page would otherwise
  // open the document at whatever scroll position that link was at.
  useEffect(() => { window.scrollTo(0, 0) }, [doc])

  if (!content) return null

  return (
    <PublicPage page="legal" onLogin={() => openModal('login', {})}>
      <article className="legal">
        <div className="wrap">
          <header className="legal-head">
            <span className="eyebrow">Legal</span>
            <h1>{content.title}</h1>
            <p className="legal-updated">Last updated {legalMeta.updated}</p>
            <p className="legal-intro">{content.intro}</p>
          </header>

          <nav className="legal-toc" aria-label="On this page">
            <span className="legal-toc-label">On this page</span>
            <ol>
              {content.sections.map((s, i) => (
                <li key={s.h}>
                  <a href={`#${content.id}-${i}`}>{s.h}</a>
                </li>
              ))}
            </ol>
          </nav>

          <div className="legal-body">
            {content.sections.map((s, i) => (
              <section key={s.h} id={`${content.id}-${i}`}>
                <h2>
                  <span className="legal-num">{i + 1}</span>
                  {s.h}
                </h2>
                {s.p.map((text) => <p key={text}>{text}</p>)}
                {s.list && (
                  <ul>
                    {s.list.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                )}
              </section>
            ))}
          </div>

          <footer className="legal-foot">
            <p>
              Questions about this document? Write to{' '}
              <a href={`mailto:${doc === 'privacy' ? legalMeta.privacyEmail : legalMeta.legalEmail}`}>
                {doc === 'privacy' ? legalMeta.privacyEmail : legalMeta.legalEmail}
              </a>
              .
            </p>
          </footer>
        </div>
      </article>
    </PublicPage>
  )
}
