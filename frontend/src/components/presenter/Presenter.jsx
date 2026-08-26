import { useCallback, useEffect, useState } from 'react'
import { CloseIcon, PlusIcon, CheckIcon, CrossIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import {
  fetchPresenterBoard, createPresenterNote, updatePresenterNote, deletePresenterNote,
} from '../../lib/user'

/**
 * The internal presenter drawer — now served from the database rather than a
 * hardcoded file, so notes can be changed mid-engagement without a deploy.
 *
 * Editing is staff-only. `can_edit` comes back on the payload and decides
 * whether the controls render, but that is presentation: every write is
 * re-checked against `User.is_staff` server-side, and a member who is not staff
 * gets a 404 from the write endpoints — they should not learn the endpoints
 * accept writes at all.
 *
 * Content is plain text with **bold** and *italic* markers. The old shape
 * nested arrays of {b}/{i} objects, which read fine but cannot be typed into a
 * textarea; markers keep the same rendering and make a note editable.
 */

const SECTIONS = [
  { key: 'decisions', section: 'decision', title: 'Decisions still open',
    fields: ['Question', 'What was built', 'The risk'] },
  { key: 'changes', section: 'change', title: 'Changed on the last call',
    fields: ['Item', 'Was', 'Now'] },
  { key: 'references', section: 'reference', title: 'Reference products',
    fields: ['Product', 'What to show', null] },
  { key: 'standing', section: 'standing', title: 'Standing note',
    fields: ['Note', null, null] },
]

/** Render **bold** and *italic* without trusting anything as HTML. */
function Rich({ value }) {
  if (!value) return null
  const parts = String(value).split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).filter(Boolean)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <b key={i}>{part.slice(2, -2)}</b>
    if (part.startsWith('*') && part.endsWith('*')) return <i key={i}>{part.slice(1, -1)}</i>
    return <span key={i}>{part}</span>
  })
}

export default function Presenter() {
  const { presenterOpen, closePresenter } = useApp()
  const [board, setBoard] = useState(null)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(null)   // note id, or `new:<section>`
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setBoard(await fetchPresenterBoard())
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  // Only fetched when the drawer is actually opened — it is internal and most
  // sessions never open it.
  useEffect(() => { if (presenterOpen && !board) load() }, [presenterOpen, board, load])

  async function save(section, id, values) {
    setBusy(true)
    try {
      if (id) await updatePresenterNote(id, values)
      else await createPresenterNote({ section, ...values })
      await load()
      setEditing(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(id) {
    setBusy(true)
    try {
      await deletePresenterNote(id)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const canEdit = !!board?.can_edit

  return (
    <aside id="presenter" className={presenterOpen ? 'open' : undefined}>
      <div className="pr-head">
        <div className="tt">
          <h2>Presenter notes</h2>
          <p>
            Only visible with this panel open. Turn it off before showing the product to anyone
            outside the project.
            {canEdit && ' You can edit these — changes are live for everyone on the project.'}
          </p>
        </div>
        <button className="pr-close" onClick={closePresenter}>
          <CloseIcon />
        </button>
      </div>

      <div className="pr-body">
        {error && <div className="inline-error">{error}</div>}
        {!board && !error && <div className="pr-note">Loading notes…</div>}

        {board && SECTIONS.map(({ key, section, title, fields }) => (
          <div className="pr-sec" key={key}>
            <div className="hd">
              {title}
              {canEdit && (
                <button
                  className="pr-add"
                  title={`Add to ${title.toLowerCase()}`}
                  onClick={() => setEditing(`new:${section}`)}
                >
                  <PlusIcon /> Add
                </button>
              )}
            </div>

            {editing === `new:${section}` && (
              <NoteForm
                fields={fields}
                busy={busy}
                onCancel={() => setEditing(null)}
                onSave={(values) => save(section, null, values)}
              />
            )}

            {board[key].length === 0 && editing !== `new:${section}` && (
              <div className="pr-note">Nothing here yet.</div>
            )}

            {board[key].map((note) => (
              editing === note.id ? (
                <NoteForm
                  key={note.id}
                  note={note}
                  fields={fields}
                  busy={busy}
                  onCancel={() => setEditing(null)}
                  onSave={(values) => save(section, note.id, values)}
                />
              ) : (
                <NoteCard
                  key={note.id}
                  note={note}
                  section={section}
                  canEdit={canEdit}
                  onEdit={() => setEditing(note.id)}
                  onDelete={() => remove(note.id)}
                />
              )
            ))}
          </div>
        ))}
      </div>
    </aside>
  )
}

function NoteCard({ note, section, canEdit, onEdit, onDelete }) {
  const controls = canEdit && (
    <span className="pr-ctl">
      <button onClick={onEdit} title="Edit">Edit</button>
      <button onClick={onDelete} title="Remove" className="danger">Remove</button>
    </span>
  )

  if (section === 'change') {
    return (
      <div className="dcard-pr row">
        <div className="q">{note.heading}{controls}</div>
        <div className="prop"><span className="was">{note.detail}</span></div>
        <div className="risk now"><Rich value={note.extra} /></div>
      </div>
    )
  }
  if (section === 'reference') {
    return (
      <div className="shot">
        <div className="nm">{note.heading}{controls}</div>
        <div className="ph">{note.detail}</div>
      </div>
    )
  }
  if (section === 'standing') {
    return <div className="pr-note"><Rich value={note.heading} />{controls}</div>
  }
  return (
    <div className="dcard-pr">
      <div className="q">{note.heading}{controls}</div>
      <div className="prop"><Rich value={note.detail} /></div>
      <div className="risk">{note.extra}</div>
    </div>
  )
}

function NoteForm({ note = null, fields, busy, onSave, onCancel }) {
  const [heading, setHeading] = useState(note?.heading ?? '')
  const [detail, setDetail] = useState(note?.detail ?? '')
  const [extra, setExtra] = useState(note?.extra ?? '')
  const [label1, label2, label3] = fields

  function submit(e) {
    e.preventDefault()
    if (!heading.trim()) return
    onSave({
      heading: heading.trim(),
      detail: label2 ? detail.trim() || null : null,
      extra: label3 ? extra.trim() || null : null,
    })
  }

  return (
    <form className="pr-form" onSubmit={submit}>
      <label>{label1}
        <textarea value={heading} onChange={(e) => setHeading(e.target.value)} rows={2} autoFocus />
      </label>
      {label2 && (
        <label>{label2}
          <textarea value={detail} onChange={(e) => setDetail(e.target.value)} rows={2} />
        </label>
      )}
      {label3 && (
        <label>{label3}
          <textarea value={extra} onChange={(e) => setExtra(e.target.value)} rows={2} />
        </label>
      )}
      <div className="pr-form-foot">
        <span className="pr-hint">**bold** and *italic* work</span>
        <button type="button" className="pr-ctl-btn" onClick={onCancel} disabled={busy}>
          <CrossIcon /> Cancel
        </button>
        <button type="submit" className="pr-ctl-btn ok" disabled={busy || !heading.trim()}>
          <CheckIcon /> {busy ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  )
}
