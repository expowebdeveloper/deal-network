import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Screen, { PageHead } from '../layout/Screen'
import Avatar from '../ui/Avatar'
import Tag from '../ui/Tag'
import { Loading, Empty, ErrorState } from '../ui/States'
import { LockIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import {
  fetchOverview, listIntroductions, respondToIntroduction, toTiles, toIntroduction,
} from '../../lib/investors'
import { fetchMandate } from '../../lib/user'
import { visibilityKey } from '../../data/investors'

/** The member's stated mandate, as the rail shows it. */
function mandateRows(mandate) {
  return [
    { k: 'Asset classes', v: mandate?.asset_classes || 'Not set' },
    { k: 'Markets', v: mandate?.markets || 'Not set' },
    { k: 'Typical raise', v: mandate?.typical_raise || 'Not set' },
    { k: 'Stage', v: mandate?.stage || 'Not set' },
    {
      k: 'Visible to',
      tag: {
        variant: (mandate?.visible_to || 'Members').toLowerCase(),
        label: mandate?.visible_to || 'Members',
      },
    },
  ]
}

export default function Investors() {
  const navigate = useNavigate()
  const { openModal } = useApp()

  const [direction, setDirection] = useState('incoming')
  const [state, setState] = useState({ status: 'loading', tiles: [], rows: [], error: null })
  const [mandate, setMandate] = useState(null)
  const [busy, setBusy] = useState(null)
  const [notice, setNotice] = useState(null)

  const load = useCallback(async (which) => {
    setState((s) => ({ ...s, status: 'loading' }))
    try {
      const [overview, intros, myMandate] = await Promise.all([
        fetchOverview(),
        listIntroductions(which),
        fetchMandate().catch(() => null),
      ])
      setMandate(myMandate)
      setState({
        status: 'ready',
        tiles: toTiles(overview),
        rows: intros.map((row) => toIntroduction(row, which)),
        error: null,
      })
    } catch (error) {
      setState({ status: 'error', tiles: [], rows: [], error })
    }
  }, [])

  useEffect(() => { load(direction) }, [direction, load])

  async function respond(id, accept) {
    setBusy(id)
    setNotice(null)
    try {
      await respondToIntroduction(id, accept)
      setNotice(accept
        ? 'Introduction accepted — they are now in your contacts as a new lead.'
        : 'Introduction declined.')
      await load(direction)
    } catch (error) {
      setNotice(error.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Screen name="investors">
      <PageHead
        title="Investors"
        actions={
          <>
            <button className="btn btn-ghost" onClick={() => navigate('/profile')}>
              Edit mandate
            </button>
            <button
              className="btn btn-primary"
              onClick={() => openModal('request-intro', { onSent: () => load(direction) })}
            >
              Request an introduction
            </button>
          </>
        }
      >
        Your investor-facing side of the network — who you are visible to, who has asked for an
        introduction, and what your stated mandate says.
      </PageHead>

      {notice && <div className="inline-error">{notice}</div>}

      {state.status === 'loading' && <Loading label="Loading your investor view…" />}
      {state.status === 'error' && (
        <ErrorState error={state.error} onRetry={() => load(direction)} />
      )}

      {state.status === 'ready' && (
        <>
          <div className="tiles">
            {state.tiles.map((t) => (
              <div className="card tile" key={t.l}>
                <div className="n">{t.n}</div>
                <div className="l">{t.l}</div>
                {t.d && <div className="d">{t.d}</div>}
              </div>
            ))}
          </div>

          <div className="inv-grid">
            <div>
              <h2 className="section-title">Introduction requests</h2>

              <div className="tabs">
                <button
                  className={`tab${direction === 'incoming' ? ' on' : ''}`}
                  onClick={() => setDirection('incoming')}
                >
                  Asked of you
                </button>
                <button
                  className={`tab${direction === 'outgoing' ? ' on' : ''}`}
                  onClick={() => setDirection('outgoing')}
                >
                  You asked
                </button>
              </div>

              {state.rows.length === 0 ? (
                <Empty title={direction === 'incoming'
                  ? 'Nobody has asked for an introduction yet'
                  : 'You have not asked for an introduction yet'}>
                  {direction === 'incoming'
                    ? 'When another member asks to be introduced, it lands here to accept or decline.'
                    : 'Ask to be introduced to someone and it will show here until they answer.'}
                </Empty>
              ) : (
                <div className="card introlist" style={{ marginBottom: 22 }}>
                  {state.rows.map((r) => (
                    <div className="intro-item" key={r.id}>
                      <Avatar initials={r.initials} color={r.color} />
                      <div className="info">
                        <div className="t">{r.title}</div>
                        <div className="s">{r.sub}</div>
                        {r.message && <div className="s">“{r.message}”</div>}
                      </div>
                      <Tag variant={r.tag.variant}>{r.tag.label}</Tag>

                      {direction === 'incoming' && r.status === 'pending' ? (
                        <>
                          <button
                            className="btn btn-ghost btn-sm"
                            data-busy={busy === r.id}
                            onClick={() => respond(r.id, false)}
                          >
                            Decline
                          </button>
                          <button
                            className="btn btn-dark btn-sm"
                            data-busy={busy === r.id}
                            onClick={() => respond(r.id, true)}
                          >
                            Accept
                          </button>
                        </>
                      ) : r.status === 'accepted' ? (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => navigate('/contacts')}
                        >
                          Open contact
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}

              <h2 className="section-title">Opportunities</h2>
              <div className="lockcard">
                <LockIcon width={1.8} />
                <h4>Deal listings and data rooms arrive soon</h4>
                <p>
                  Right now the network is about people and relationships. Publishing live
                  opportunities, uploading documents and granting controlled access is the next
                  thing we are building.
                </p>
              </div>
            </div>

            <aside className="inv-rail">
              <div className="card mandate" style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 13, fontWeight: 720, marginBottom: 14 }}>
                  Your stated mandate
                </h3>
                {mandateRows(mandate).map((row) => (
                  <div className="mandate-row" key={row.k}>
                    <span className="k">{row.k}</span>
                    <span className="v">
                      {row.tag ? <Tag variant={row.tag.variant}>{row.tag.label}</Tag> : row.v}
                    </span>
                  </div>
                ))}
              </div>

              <div className="card rail-card">
                <h3>Who can see what</h3>
                {visibilityKey.map((row) => (
                  <div className="rail-item" style={{ alignItems: 'flex-start' }} key={row.tag.label}>
                    <Tag variant={row.tag.variant}>{row.tag.label}</Tag>
                    <div style={{ flex: 1 }}>
                      <div className="s" style={{ margin: 0 }}>{row.text}</div>
                    </div>
                  </div>
                ))}
              </div>
            </aside>
          </div>
        </>
      )}
    </Screen>
  )
}
