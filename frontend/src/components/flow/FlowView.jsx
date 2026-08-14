import { Fragment } from 'react'
import { useNavigate } from 'react-router-dom'
import Tag from '../ui/Tag'
import { ArrowRightIcon, ArrowDownIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import { bands, legend, TAGS } from '../../data/flow'

function Node({ node, onActivate }) {
  const clickable = !node.locked && node.action
  const classes = ['node', node.locked && 'locked', node.cls].filter(Boolean).join(' ')

  return (
    <div className={classes} onClick={clickable ? onActivate : undefined}>
      <div className="nt">{node.title}</div>
      <div className="nd">{node.desc}</div>
      {node.tags && (
        <div className="ntags">
          {node.tags.map((key) => (
            <Tag key={key} variant={TAGS[key].variant}>{TAGS[key].label}</Tag>
          ))}
        </div>
      )}
    </div>
  )
}

export default function FlowView() {
  const { closeFlow, openModal, signOut } = useApp()
  const navigate = useNavigate()

  // Turn a node's action descriptor into what actually happens on click.
  function run(action) {
    if (!action) return
    if (action.signOut) return signOut()
    if (action.modal) return openModal(action.modal, action.props)
    if (action.nav) {
      closeFlow()
      navigate(action.nav)
    }
  }

  return (
    <div id="flow">
      <div className="flow-top">
        <div style={{ flex: 1 }}>
          <h2>How it connects</h2>
          <p>Every step a member moves through, and the information each one creates. Click any box to open it.</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={closeFlow}>Close</button>
      </div>

      <div className="flow-scroll">
        <div className="flow-inner">
          <div className="flow-legend">
            <span className="li lead">Data created:</span>
            {legend.map((l) => (
              <span className="li" key={l.key}>
                <Tag variant={l.variant}>{l.label}</Tag> {l.note}
              </span>
            ))}
          </div>

          {bands.map((band, bi) => (
            <Fragment key={band.label}>
              <div className="band">
                <div className="band-label">
                  <span className="txt">{band.label}</span>
                  <span className="ln" />
                </div>
                <div className="band-row">
                  {band.nodes.map((node, ni) => (
                    <Fragment key={node.title}>
                      <Node node={node} onActivate={() => run(node.action)} />
                      {ni < band.nodes.length - 1 && (
                        <div className="arrow"><ArrowRightIcon /></div>
                      )}
                    </Fragment>
                  ))}
                </div>
              </div>

              {bi < bands.length - 1 && (
                <div className="vgap"><ArrowDownIcon /></div>
              )}
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  )
}
