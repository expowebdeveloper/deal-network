import { CloseIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import { openDecisions, changedRows, referenceShots, standingNote } from '../../data/presenter'

/** Renders a run of text where some spans are bold or italic. */
function Rich({ value }) {
  if (typeof value === 'string') return value
  return value.map((part, i) => {
    if (typeof part === 'string') return <span key={i}>{part}</span>
    if (part.b) return <b key={i}>{part.b}</b>
    return <i key={i}>{part.i}</i>
  })
}

export default function Presenter() {
  const { presenterOpen, closePresenter } = useApp()

  return (
    <aside id="presenter" className={presenterOpen ? 'open' : undefined}>
      <div className="pr-head">
        <div className="tt">
          <h2>Presenter notes</h2>
          <p>
            Only visible with this panel open. Turn it off before showing the product to anyone
            outside the project.
          </p>
        </div>
        <button className="pr-close" onClick={closePresenter}>
          <CloseIcon />
        </button>
      </div>

      <div className="pr-body">
        <div className="pr-sec">
          <div className="hd">Decisions still open</div>
          {openDecisions.map((d) => (
            <div className="dcard-pr" key={d.q}>
              <div className="q">{d.q}</div>
              <div className="prop"><Rich value={d.prop} /></div>
              <div className="risk">{d.risk}</div>
            </div>
          ))}
        </div>

        <div className="pr-sec">
          <div className="hd">Changed on the last call</div>
          <table className="pr-table">
            <thead>
              <tr><th>Item</th><th>Was</th><th>Now</th></tr>
            </thead>
            <tbody>
              {changedRows.map((r) => (
                <tr key={r.item}>
                  <td className="item">{r.item}</td>
                  <td>{r.was}</td>
                  <td className="now"><Rich value={r.now} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="pr-sec">
          <div className="hd">Reference products — screenshots to add</div>
          {referenceShots.map((s) => (
            <div className="shot" key={s.nm}>
              <div className="nm">{s.nm}</div>
              <div className="ph">{s.ph}</div>
            </div>
          ))}
        </div>

        <div className="pr-sec">
          <div className="hd">Standing note</div>
          <div className="pr-note">{standingNote}</div>
        </div>
      </div>
    </aside>
  )
}
