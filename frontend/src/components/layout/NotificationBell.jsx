import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Avatar from '../ui/Avatar'
import { BellIcon } from '../icons/Icons'
import { timeAgo } from '../../lib/feed'
import {
  fetchNotifications, fetchUnreadCount, markNotificationRead, markAllNotificationsRead,
} from '../../lib/user'

/**
 * The header bell: unread count, and the list behind it.
 *
 * The count is polled rather than pushed — there is no websocket in the product
 * yet, and a 60s poll of one indexed COUNT is far cheaper than the machinery a
 * live channel would need. The interval is paused while the tab is hidden, so a
 * window left open overnight is not still asking.
 *
 * Opening the panel fetches the list; it is not kept warm, because the badge is
 * the only part that has to be current when the panel is shut.
 */

const POLL_MS = 60_000

export default function NotificationBell() {
  const navigate = useNavigate()
  const boxRef = useRef(null)

  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [state, setState] = useState({ status: 'idle', items: [] })

  const refreshCount = useCallback(async () => {
    try {
      const { unread: n } = await fetchUnreadCount()
      setUnread(n)
    } catch {
      /* a failed count must not break the header */
    }
  }, [])

  useEffect(() => {
    refreshCount()
    let timer = null
    const start = () => { timer ??= setInterval(refreshCount, POLL_MS) }
    const stop = () => { if (timer) { clearInterval(timer); timer = null } }

    // Polling a hidden tab wakes the device and the server for nothing.
    const onVisibility = () => (document.hidden ? stop() : (refreshCount(), start()))
    if (!document.hidden) start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => { stop(); document.removeEventListener('visibilitychange', onVisibility) }
  }, [refreshCount])

  useEffect(() => {
    function onDown(e) { if (!boxRef.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  async function toggle() {
    const next = !open
    setOpen(next)
    if (!next) return
    setState({ status: 'loading', items: [] })
    try {
      const feed = await fetchNotifications({ limit: 15 })
      setState({ status: 'ready', items: feed.items })
      setUnread(feed.unread)
    } catch {
      setState({ status: 'error', items: [] })
    }
  }

  async function pick(n) {
    setOpen(false)
    if (!n.read_at) {
      // Optimistic: the row is already gone from view, so waiting for the
      // server before dimming it would only make the badge lag.
      setUnread((v) => Math.max(0, v - 1))
      markNotificationRead(n.id).catch(() => refreshCount())
    }
    if (n.link) navigate(n.link)
  }

  async function readAll() {
    setUnread(0)
    setState((s) => ({
      ...s,
      items: s.items.map((n) => ({ ...n, read_at: n.read_at || new Date().toISOString() })),
    }))
    try { await markAllNotificationsRead() } catch { refreshCount() }
  }

  return (
    <div className="nb" ref={boxRef}>
      <button
        className={`icon-btn${open ? ' on' : ''}`}
        title="Notifications"
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        onClick={toggle}
      >
        <BellIcon />
        {unread > 0 && <span className="nb-badge">{unread > 9 ? '9+' : unread}</span>}
      </button>

      {open && (
        <div className="nb-panel" role="dialog" aria-label="Notifications">
          <div className="nb-head">
            <span>Notifications</span>
            {unread > 0 && (
              <button className="nb-all" onClick={readAll}>Mark all read</button>
            )}
          </div>

          {state.status === 'loading' && <div className="nb-note">Loading…</div>}
          {state.status === 'error' && <div className="nb-note">Could not load these.</div>}
          {state.status === 'ready' && state.items.length === 0 && (
            <div className="nb-note">
              Nothing yet. Connection requests, join requests and introductions land here.
            </div>
          )}

          {state.items.map((n) => (
            <button
              key={n.id}
              className={`nb-row${n.read_at ? '' : ' unread'}`}
              onClick={() => pick(n)}
            >
              {n.actor
                ? <Avatar initials={n.actor.initials} color={n.actor.avatar_color} size="sm" />
                : <span className="nb-dot" aria-hidden="true" />}
              <span className="nb-text">
                <span className="nb-title">{n.title}</span>
                {n.body && <span className="nb-body">{n.body}</span>}
                <span className="nb-when">{timeAgo(n.created_at)}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
