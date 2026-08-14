/** One routed screen. Mirrors the `.screen.on` wrapper so the enter animation runs. */
export default function Screen({ name, narrow = false, children }) {
  return (
    <section className="screen on" data-screen={name}>
      <div className={`page${narrow ? ' page-narrow' : ''}`}>{children}</div>
    </section>
  )
}

/** Title block at the top of a screen; `actions` sit on the right. */
export function PageHead({ title, children, actions }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {children && <p>{children}</p>}
      </div>
      {actions && (
        <>
          <div className="sp" />
          {actions}
        </>
      )}
    </div>
  )
}
