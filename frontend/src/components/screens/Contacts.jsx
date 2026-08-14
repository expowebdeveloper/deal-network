import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Screen, { PageHead } from '../layout/Screen'
import Avatar from '../ui/Avatar'
import { Loading, Empty, ErrorState } from '../ui/States'
import { PlusIcon, DragIcon, LockIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import {
  listContacts, fetchPipeline, moveContact, toContact, isUpgradeRequired,
} from '../../lib/contacts'
import { fetchEntitlements } from '../../lib/feed'
import { STAGES, STAGE_CLASS } from '../../data/contacts'

const isTouch = typeof window !== 'undefined' && window.matchMedia('(hover:none)').matches

function ContactTable({ rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Contact</th><th>Role</th><th>Market</th><th>Stage</th><th>Source</th><th>Last touch</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id}>
              <td>
                <div className="td-name">
                  <Avatar initials={c.initials} color={c.color} size="sm" />
                  <div>
                    <div className="n">{c.name}</div>
                    <div className="c">{c.company}</div>
                  </div>
                </div>
              </td>
              <td>{c.role}</td>
              <td>{c.market}</td>
              <td><span className={`stage ${STAGE_CLASS[c.stage]}`}>{c.stage}</span></td>
              <td>{c.source}</td>
              <td>{c.touch}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * Pipeline board. Cards move by drag-and-drop on pointer devices and by
 * tap-card-then-tap-column everywhere — the latter is the only option on touch.
 */
function Board({ rows, onMove }) {
  const [dragging, setDragging] = useState(null)
  const [dragOver, setDragOver] = useState(null)
  const [picked, setPicked] = useState(null)

  const byStage = useMemo(() => {
    const map = Object.fromEntries(STAGES.map((s) => [s, []]))
    rows.forEach((c) => map[c.stage]?.push(c))
    return map
  }, [rows])

  const drop = useCallback((stage) => {
    setDragOver(null)
    if (dragging) onMove(dragging, stage)
    setDragging(null)
  }, [dragging, onMove])

  function onColumnClick(stage) {
    if (!picked) return
    onMove(picked, stage)
    setPicked(null)
  }

  function onCardClick(e, id) {
    e.stopPropagation()
    setPicked((cur) => (cur === id ? null : id))
  }

  return (
    <>
      <div className="board-hint">
        <DragIcon />
        <span>
          {isTouch
            ? 'Tap a card, then tap the column you want to move it to.'
            : 'Drag a card between columns to move a relationship along.'}
        </span>
      </div>

      <div className={`board${picked ? ' picking' : ''}`}>
        {STAGES.map((stage) => (
          <div
            key={stage}
            className={`col${dragOver === stage ? ' dragover' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(stage) }}
            onDragLeave={() => setDragOver((s) => (s === stage ? null : s))}
            onDrop={(e) => { e.preventDefault(); drop(stage) }}
            onClick={() => onColumnClick(stage)}
          >
            <div className="col-head">
              <span className="t">{stage}</span>
              <span className="n">{byStage[stage].length}</span>
            </div>

            {byStage[stage].map((c) => (
              <div
                key={c.id}
                className={[
                  'dcard',
                  dragging === c.id && 'dragging',
                  picked === c.id && 'picked',
                ].filter(Boolean).join(' ')}
                draggable
                onDragStart={() => setDragging(c.id)}
                onDragEnd={() => setDragging(null)}
                onClick={(e) => onCardClick(e, c.id)}
              >
                <div className="t">{c.name}</div>
                <div className="c">{c.company} · {c.role}</div>
                <div className="f">
                  <Avatar initials={c.initials} color={c.color} size="sm" className="dcard-avatar" />
                  <span className="tag">{c.short}</span>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </>
  )
}

/** Shown in place of the board when the plan does not carry it. */
function PipelineLocked() {
  const navigate = useNavigate()
  return (
    <div className="locked-panel card">
      <LockIcon />
      <h3>The pipeline board is a Member feature</h3>
      <p>
        Your contacts are all still here in the List tab. Move to Member to work them as a
        board — five stages, drag a card to move a relationship along.
      </p>
      <button className="btn btn-primary" onClick={() => navigate('/plans')}>See plans</button>
    </div>
  )
}

export default function Contacts() {
  const { openModal } = useApp()
  const [tab, setTab] = useState('list')
  const [state, setState] = useState({ status: 'loading', rows: [], error: null })
  const [plan, setPlan] = useState(null)
  const [notice, setNotice] = useState(null)

  const load = useCallback(async () => {
    setState((s) => ({ ...s, status: 'loading' }))
    try {
      const [page, entitlements] = await Promise.all([
        listContacts(),
        fetchEntitlements().catch(() => null),
      ])
      setPlan(entitlements)
      setState({ status: 'ready', rows: page.items.map(toContact), error: null })
    } catch (error) {
      setState({ status: 'error', rows: [], error })
    }
  }, [])

  useEffect(() => { load() }, [load])

  // The board is its own call, so it is also where the plan gate shows up.
  const [board, setBoard] = useState({ status: 'idle', rows: [], locked: false })
  const loadBoard = useCallback(async () => {
    setBoard((b) => ({ ...b, status: 'loading' }))
    try {
      const pipeline = await fetchPipeline()
      const rows = pipeline.columns.flatMap((column) => column.contacts.map(toContact))
      setBoard({ status: 'ready', rows, locked: false })
    } catch (error) {
      if (isUpgradeRequired(error)) setBoard({ status: 'ready', rows: [], locked: true })
      else setBoard({ status: 'error', rows: [], locked: false, error })
    }
  }, [])

  useEffect(() => {
    if (tab === 'board') loadBoard()
  }, [tab, loadBoard])

  /** Optimistic: the card moves at once, and goes back if the save fails. */
  const move = useCallback(async (id, stage) => {
    const before = board.rows
    const item = before.find((c) => c.id === id)
    if (!item || item.stage === stage) return
    setBoard((b) => ({
      ...b,
      rows: [...b.rows.filter((c) => c.id !== id), { ...item, stage }],
    }))
    setNotice(null)
    try {
      await moveContact(id, stage)
      load() // keep the list tab's "last touch" honest
    } catch (error) {
      setBoard((b) => ({ ...b, rows: before }))
      setNotice(error.message)
    }
  }, [board.rows, load])

  const limit = plan?.contact_limit ?? null
  const used = state.rows.length
  const full = limit !== null && used >= limit

  function addContact() {
    openModal('add-contact', { onAdded: () => load() })
  }

  return (
    <Screen name="contacts">
      <PageHead
        title="Contacts"
        actions={
          <>
            <button className="btn btn-ghost">Import</button>
            <button className="btn btn-primary" onClick={addContact} data-busy={false}>
              <PlusIcon style={{ width: 15, height: 15 }} />
              Add contact
            </button>
          </>
        }
      >
        Your own relationship record. People you meet through communities land here, and you move
        them along at your own pace.
      </PageHead>

      {limit !== null && (
        <div className={`quota${full ? ' full' : ''}`}>
          {used} of {limit} contacts used on {plan.plan_name}
          {full && ' — move to Member for unlimited contacts.'}
        </div>
      )}

      {notice && <div className="inline-error">{notice}</div>}

      <div className="tabs">
        <button className={`tab${tab === 'list' ? ' on' : ''}`} onClick={() => setTab('list')}>List</button>
        <button className={`tab${tab === 'board' ? ' on' : ''}`} onClick={() => setTab('board')}>Pipeline</button>
      </div>

      {state.status === 'loading' && <Loading label="Loading contacts…" />}
      {state.status === 'error' && <ErrorState error={state.error} onRetry={load} />}

      {state.status === 'ready' && tab === 'list' && (
        state.rows.length === 0 ? (
          <Empty
            title="No contacts yet"
            action={
              <button className="btn btn-primary btn-sm" onClick={addContact}>Add your first</button>
            }
          >
            People you meet through communities land here, and anyone you add yourself.
          </Empty>
        ) : (
          <ContactTable rows={state.rows} />
        )
      )}

      {state.status === 'ready' && tab === 'board' && (
        board.locked ? <PipelineLocked />
          : board.status === 'loading' ? <Loading label="Loading the board…" />
            : board.status === 'error' ? <ErrorState error={board.error} onRetry={loadBoard} />
              : <Board rows={board.rows} onMove={move} />
      )}
    </Screen>
  )
}
