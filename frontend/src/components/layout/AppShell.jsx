import { useEffect, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import BottomNav from './BottomNav'
import { useApp } from '../../context/AppContext'

export default function AppShell({ locked = false, fullScreen = false }) {
  const { pathname } = useLocation()
  const { closeFlow } = useApp()
  const scrollRef = useRef(null)

  // Each screen starts at the top, and changing screens closes the flow overlay.
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0
    closeFlow()
  }, [pathname, closeFlow])

  // Before a plan is chosen or when viewing in full screen mode,
  // the sidebar is hidden so the page displays full screen.
  if (locked || fullScreen) {
    return (
      <div id="app" className="app-locked app-fullscreen">
        <div className="maincol">
          <Topbar locked={locked} fullScreen={fullScreen} />
          <div className="screenwrap" ref={scrollRef}>
            <Outlet />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div id="app">
      <Sidebar />

      <div className="maincol">
        <Topbar />
        <div className="screenwrap" ref={scrollRef}>
          <Outlet />
        </div>
      </div>

      <BottomNav />
    </div>
  )
}
