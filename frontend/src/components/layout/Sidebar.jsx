import { NavLink, useNavigate } from 'react-router-dom'
import { BrandMark } from '../icons/Icons'
import Avatar from '../ui/Avatar'
import { useEffect, useState } from 'react'
import { sidebarGroups } from '../../data/nav'
import { useApp } from '../../context/AppContext'
import { toDisplayUser } from '../../lib/user'
import { api } from '../../lib/api'

export default function Sidebar() {
  const navigate = useNavigate()
  const { user } = useApp()
  const currentUser = toDisplayUser(user)

  // Live badge counts. `total` comes back on the page envelope, so limit=1 is enough.
  const [counts, setCounts] = useState({})
  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.get('/api/communities?joined=true&limit=1').catch(() => null),
      api.get('/api/contacts?limit=1').catch(() => null),
    ]).then(([communities, contacts]) => {
      if (cancelled) return
      setCounts({ communities: communities?.total, contacts: contacts?.total })
    })
    return () => { cancelled = true }
  }, [])

  if (!currentUser) return null

  return (
    <aside className="sidebar">
      <div className="sb-head">
        <BrandMark />
        <span className="brand-name">Deal Network</span>
      </div>

      <nav className="sb-nav">
        {sidebarGroups.map((group, gi) => (
          <div className="sb-group" key={group.label ?? gi}>
            {group.label && <div className="sb-label">{group.label}</div>}
            {group.items.map(({ to, label, Icon, countKey, soon, end }) =>
              soon ? (
                <div className="sb-item locked" key={label}>
                  <Icon />
                  <span>{label}</span>
                  <span className="sb-soon">SOON</span>
                </div>
              ) : (
                <NavLink
                  key={label}
                  to={to}
                  end={end}
                  className={({ isActive }) => `sb-item${isActive ? ' on' : ''}`}
                >
                  <Icon />
                  <span>{label}</span>
                  {counts[countKey] > 0 && (
                    <span className="sb-count">{counts[countKey]}</span>
                  )}
                </NavLink>
              ),
            )}
          </div>
        ))}
      </nav>

      <div className="sb-foot">
        <button className="sb-user" onClick={() => navigate('/profile')}>
          <Avatar initials={currentUser.initials} color={currentUser.color} size="sm" />
          <div className="txt">
            <div className="nm">{currentUser.name}</div>
            <div className="rl">{currentUser.company}</div>
          </div>
        </button>
      </div>
    </aside>
  )
}
