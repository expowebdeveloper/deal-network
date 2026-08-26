import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Avatar from '../ui/Avatar'
import { SearchIcon } from '../icons/Icons'
import { search } from '../../lib/feed'

/**
 * The header search: people, communities and your own contacts in one list.
 *
 * Two things this has to get right, both of which are about typing fast:
 *
 *  1. **Ordering.** A request per keystroke means an early slow reply can land
 *     after a later fast one and overwrite fresher results. Each new query
 *     aborts the previous one, so a stale reply never arrives at all.
 *  2. **Not searching on every character.** The input is debounced, and the
 *     server ignores anything under two characters, so a single letter never
 *     scans three tables.
 *
 * Results are one flat, ordered list behind the scenes even though they render
 * in three groups — that is what lets the arrow keys walk the whole dropdown
 * rather than getting stuck inside a section.
 */

const DEBOUNCE_MS = 220
const MIN_QUERY = 2

export default function GlobalSearch() {
  const navigate = useNavigate()
  const boxRef = useRef(null)
  const inputRef = useRef(null)
  const abortRef = useRef(null)

  const [term, setTerm] = useState('')
  const [results, setResults] = useState(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [cursor, setCursor] = useState(-1)

  // Flat list in render order, so ↑/↓ can cross group boundaries.
  const rows = useMemo(() => {
    if (!results) return []
    return [
      ...results.people.map((p) => ({ kind: 'person', item: p })),
      ...results.communities.map((c) => ({ kind: 'community', item: c })),
      ...results.contacts.map((c) => ({ kind: 'contact', item: c })),
    ]
  }, [results])

  useEffect(() => {
    const query = term.trim()
    if (query.length < MIN_QUERY) {
      abortRef.current?.abort()
      setResults(null)
      setBusy(false)
      return undefined
    }

    setBusy(true)
    const handle = setTimeout(async () => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      try {
        const data = await search(query, { signal: controller.signal })
        setResults(data)
        setCursor(-1)
      } catch (error) {
        // Our own cancellation — a fresher query is already running.
        if (error?.name !== 'AbortError') setResults(null)
      } finally {
        if (!controller.signal.aborted) setBusy(false)
      }
    }, DEBOUNCE_MS)

    return () => clearTimeout(handle)
  }, [term])

  // Close when the click lands outside the whole box, not just the input —
  // otherwise choosing a result would dismiss the list before the click ran.
  useEffect(() => {
    function onDocumentDown(event) {
      if (!boxRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocumentDown)
    return () => document.removeEventListener('mousedown', onDocumentDown)
  }, [])

  const go = useCallback((row) => {
    setOpen(false)
    setTerm('')
    setResults(null)
    inputRef.current?.blur()
    if (row.kind === 'person') navigate(`/members/${row.item.id}`)
    // The community opens in its own dialog on the Communities screen, which
    // reads this parameter on mount.
    else if (row.kind === 'community') navigate(`/communities?open=${row.item.slug}`)
    else navigate(`/contacts?focus=${row.item.id}`)
  }, [navigate])

  function onKeyDown(event) {
    if (event.key === 'Escape') { setOpen(false); inputRef.current?.blur(); return }
    if (!open || rows.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setCursor((c) => (c + 1) % rows.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setCursor((c) => (c <= 0 ? rows.length - 1 : c - 1))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      go(rows[cursor >= 0 ? cursor : 0])
    }
  }

  const query = term.trim()
  const showPanel = open && query.length >= MIN_QUERY
  let index = -1

  return (
    <div className="searchbox gs" ref={boxRef}>
      <SearchIcon width={2} style={{ width: 15, height: 15 }} />
      <input
        ref={inputRef}
        value={term}
        placeholder="Search people, communities, contacts"
        onChange={(e) => { setTerm(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        aria-label="Search people, communities and contacts"
        aria-expanded={showPanel}
        role="combobox"
        aria-controls="gs-results"
      />

      {showPanel && (
        <div className="gs-panel" id="gs-results" role="listbox">
          {busy && !results && <div className="gs-note">Searching…</div>}

          {results && results.total === 0 && !busy && (
            <div className="gs-note">
              Nothing matches “{query}”.
            </div>
          )}

          {results?.people.length > 0 && (
            <Group label="People">
              {results.people.map((p) => {
                index += 1
                return (
                  <Row key={p.id} active={index === cursor} onPick={() => go({ kind: 'person', item: p })}>
                    <Avatar initials={p.initials} color={p.avatar_color} size="sm" />
                    <span className="gs-name">{p.name}</span>
                    <span className="gs-sub">
                      {[p.role, p.company, p.location].filter(Boolean).join(' · ')}
                    </span>
                  </Row>
                )
              })}
            </Group>
          )}

          {results?.communities.length > 0 && (
            <Group label="Communities">
              {results.communities.map((c) => {
                index += 1
                return (
                  <Row key={c.id} active={index === cursor} onPick={() => go({ kind: 'community', item: c })}>
                    <Avatar initials={c.initials} color={c.banner} size="sm" />
                    <span className="gs-name">{c.name}</span>
                    <span className="gs-sub">
                      {c.location} · {c.member_count} members{c.joined ? ' · joined' : ''}
                    </span>
                  </Row>
                )
              })}
            </Group>
          )}

          {results?.contacts.length > 0 && (
            <Group label="Your contacts">
              {results.contacts.map((c) => {
                index += 1
                return (
                  <Row key={c.id} active={index === cursor} onPick={() => go({ kind: 'contact', item: c })}>
                    <Avatar initials={c.initials} color={c.avatar_color} size="sm" />
                    <span className="gs-name">{c.name}</span>
                    <span className="gs-sub">
                      {[c.company, c.stage].filter(Boolean).join(' · ')}
                    </span>
                  </Row>
                )
              })}
            </Group>
          )}
        </div>
      )}
    </div>
  )
}

function Group({ label, children }) {
  return (
    <div className="gs-group">
      <div className="gs-label">{label}</div>
      {children}
    </div>
  )
}

function Row({ active, onPick, children }) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      className={`gs-row${active ? ' on' : ''}`}
      // mousedown, not click: the input's blur would otherwise close the panel
      // before the click could land.
      onMouseDown={(e) => { e.preventDefault(); onPick() }}
    >
      {children}
    </button>
  )
}
