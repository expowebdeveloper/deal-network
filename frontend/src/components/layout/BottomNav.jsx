import { NavLink } from 'react-router-dom'
import { bottomNavItems } from '../../data/nav'

export default function BottomNav() {
  return (
    <nav className="bottomnav">
      {bottomNavItems.map(({ to, label, Icon, end }) => (
        <NavLink key={label} to={to} end={end} className={({ isActive }) => `bn-item${isActive ? ' on' : ''}`}>
          <Icon />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
