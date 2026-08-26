import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Screen from '../layout/Screen'
import Avatar from '../ui/Avatar'
import { Loading, ErrorState } from '../ui/States'
import { useApp } from '../../context/AppContext'
import { api } from '../../lib/api'
import { initialsFor } from '../../lib/user'

/**
 * Another member's profile, at `/members/:userId`.
 *
 * Not the same screen as `/profile`, and that distinction is the whole point:
 * `Profile` is yours — it carries Edit profile and the Field visibility panel.
 * This one is read-only, and shows only what the member chose to share.
 *
 * Until this existed, the View button on every member card navigated to
 * `/profile`, so looking at anyone showed you *your own* profile with their
 * name nowhere in sight.
 *
 * Fields the member marked Private come back empty from the API — the server
 * filters them, this page never receives them. So "not shared" here means
 * genuinely absent, not hidden with CSS.
 */
export default function MemberProfile() {
  const { userId } = useParams()
  const navigate = useNavigate()
  const { user, openModal } = useApp()

  const [state, setState] = useState({ status: 'loading', member: null, error: null })

  const load = useCallback(async () => {
    setState({ status: 'loading', member: null, error: null })
    try {
      setState({ status: 'ready', member: await api.get(`/api/members/${userId}`), error: null })
    } catch (error) {
      setState({ status: 'error', member: null, error })
    }
  }, [userId])

  useEffect(() => { load() }, [load])

  // Landing on your own id is not an error — send them to the editable screen.
  useEffect(() => {
    if (user?.id && userId === user.id) navigate('/profile', { replace: true })
  }, [user?.id, userId, navigate])

  const m = state.member

  return (
    <Screen name="member-profile">
      <button className="btn btn-ghost btn-sm mp-back" onClick={() => navigate('/members')}>
        ← Back to members
      </button>

      {state.status === 'loading' && <Loading label="Loading profile…" />}
      {state.status === 'error' && (
        <ErrorState
          error={state.error?.status === 404
            ? new Error('That member does not exist, or has left the network.')
            : state.error}
          onRetry={load}
        />
      )}

      {state.status === 'ready' && m && (
        <>
          <div className="card mp-head">
            <div className="mp-cover" />
            <div className="mp-id">
              <Avatar
                initials={m.initials || initialsFor(m.name, m.email || '')}
                color={m.avatar_color}
                size="xl"
              />
              <div className="mp-name">
                <h1>{m.name}</h1>
                <div className="mp-role">
                  {[m.role, m.company].filter(Boolean).join(' · ') || 'Member'}
                </div>
                <div className="mp-loc">
                  {[m.location, m.focus].filter(Boolean).join(' · ') || '—'}
                </div>
              </div>
              <button
                className="btn btn-dark"
                onClick={() => openModal('connect', {
                  person: {
                    id: m.id, name: m.name, initials: m.initials,
                    color: m.avatar_color, role: m.role, company: m.company,
                  },
                })}
              >
                Connect
              </button>
            </div>

            <div className="mp-stats">
              <div><b>{m.completed_projects ?? 0}</b><span>Completed projects</span></div>
              <div><b>{m.units_delivered ?? 0}</b><span>Units delivered</span></div>
              <div><b>{m.active_projects ?? 0}</b><span>Active projects</span></div>
              <div><b>{m.profile_views ?? 0}</b><span>Profile views</span></div>
            </div>
          </div>

          {m.bio && (
            <div className="card mp-block">
              <h2>About</h2>
              <p>{m.bio}</p>
            </div>
          )}

          <div className="card mp-block">
            <h2>Details</h2>
            <dl className="mp-facts">
              <div><dt>Role</dt><dd>{m.role || 'Not set'}</dd></div>
              <div><dt>Company</dt><dd>{m.company || <Withheld />}</dd></div>
              <div><dt>Markets</dt><dd>{m.location || <Withheld />}</dd></div>
              <div><dt>Focus</dt><dd>{m.focus || 'Not set'}</dd></div>
              {/* Email is Private by default, so this is usually withheld. */}
              <div><dt>Email</dt><dd>{m.email || <Withheld />}</dd></div>
            </dl>
            <p className="mp-note">
              Members choose what to share. Anything they have kept private is not
              shown here and is not sent to your browser.
            </p>
          </div>
        </>
      )}
    </Screen>
  )
}

/** A field the member has not made visible to you. */
function Withheld() {
  return <span className="mp-withheld">Not shared</span>
}
