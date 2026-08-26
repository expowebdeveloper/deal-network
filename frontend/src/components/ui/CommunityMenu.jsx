import { useState, useRef, useEffect } from 'react'
import { MoreVerticalIcon, SettingsIcon, ForumIcon, CommunitiesIcon, CrossIcon } from '../icons/Icons'
import { canManageRoles, isDraft } from '../../lib/communities'

export default function CommunityMenu({
  community,
  onOpenSettings,
  onOpenTab,
  onJoin,
  onLeave,
  busy = false,
  align = 'right',
  variant = 'card', // 'card' | 'header'
}) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  function handleTrigger(e) {
    e.stopPropagation()
    setOpen((prev) => !prev)
  }

  function handleSelect(action, e) {
    e.stopPropagation()
    setOpen(false)
    action()
  }

  const isOwnerOrAdmin = canManageRoles(community?.myRole)

  return (
    <div className={`cmenu-wrap ${variant}`} ref={menuRef}>
      <button
        type="button"
        className={`cmenu-btn ${open ? 'active' : ''}`}
        aria-label="Community options"
        title="Options"
        onClick={handleTrigger}
      >
        <MoreVerticalIcon style={{ width: 18, height: 18 }} />
      </button>

      {open && (
        <div className={`cmenu-dropdown align-${align}`} onClick={(e) => e.stopPropagation()}>
          <div className="cmenu-header">
            <span className="cmenu-title">{community.name}</span>
            {isDraft(community) && <span className="cmenu-badge">DRAFT</span>}
          </div>

          <div className="cmenu-items">
            {/* Settings (Opens Dedicated Settings Drawer) */}
            {isOwnerOrAdmin && onOpenSettings && (
              <button
                type="button"
                className="cmenu-item highlight"
                onClick={(e) => handleSelect(onOpenSettings, e)}
              >
                <SettingsIcon style={{ width: 16, height: 16 }} />
                <span>Settings</span>
              </button>
            )}

            {/* View Discussion */}
            {onOpenTab && (
              <button
                type="button"
                className="cmenu-item"
                onClick={(e) => handleSelect(() => onOpenTab('Discussion'), e)}
              >
                <ForumIcon style={{ width: 16, height: 16 }} />
                <span>View Discussion</span>
              </button>
            )}

            {/* View Channels */}
            {onOpenTab && (
              <button
                type="button"
                className="cmenu-item"
                onClick={(e) => handleSelect(() => onOpenTab('Channels'), e)}
              >
                <span className="cmenu-icon-text">#</span>
                <span>View Channels</span>
              </button>
            )}

            {/* View Members */}
            {onOpenTab && (
              <button
                type="button"
                className="cmenu-item"
                onClick={(e) => handleSelect(() => onOpenTab('Members'), e)}
              >
                <CommunitiesIcon style={{ width: 16, height: 16 }} />
                <span>View Members</span>
              </button>
            )}

            <div className="cmenu-divider" />

            {/* Membership actions */}
            {!isDraft(community) && (
              community.joined ? (
                <button
                  type="button"
                  className="cmenu-item danger"
                  disabled={busy}
                  onClick={(e) => handleSelect(onLeave, e)}
                >
                  <CrossIcon style={{ width: 15, height: 15 }} />
                  <span>Leave Community</span>
                </button>
              ) : community.pending ? (
                <button
                  type="button"
                  className="cmenu-item"
                  disabled={busy}
                  onClick={(e) => handleSelect(onLeave, e)}
                >
                  <CrossIcon style={{ width: 15, height: 15 }} />
                  <span>Withdraw Request</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="cmenu-item primary"
                  disabled={busy}
                  onClick={(e) => handleSelect(onJoin, e)}
                >
                  <span>{community.joinPolicy === 'request' ? 'Request to Join' : 'Join Community'}</span>
                </button>
              )
            )}
          </div>
        </div>
      )}
    </div>
  )
}
