import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Screen, { PageHead } from '../layout/Screen'
import Chip from '../ui/Chip'
import Avatar from '../ui/Avatar'
import { Loading, Empty, ErrorState } from '../ui/States'
import { useApp } from '../../context/AppContext'
import { api } from '../../lib/api'
import { memberFilters } from '../../data/members'

function toMember(m) {
  return {
    id: m.id,
    name: m.name,
    initials: m.initials,
    color: m.avatar_color,
    role: m.role || 'Member',
    company: m.company || '—',
    location: m.location || '—',
  }
}

export default function Members() {
  const { openModal } = useApp()
  const navigate = useNavigate()
  const [role, setRole] = useState('all')
  const [state, setState] = useState({ status: 'loading', items: [], error: null })
  const requestSeq = useRef(0)

  const load = useCallback(async (which) => {
    const seq = ++requestSeq.current
    setState((s) => ({ ...s, status: 'loading' }))
    try {
      const params = new URLSearchParams({ limit: '48' })
      if (which !== 'all') params.set('role', which)
      const page = await api.get(`/api/members?${params}`)
      if (seq !== requestSeq.current) return
      setState({ status: 'ready', items: page.items.map(toMember), error: null })
    } catch (error) {
      if (seq !== requestSeq.current) return
      setState({ status: 'error', items: [], error })
    }
  }, [])

  useEffect(() => { load(role) }, [role, load])

  return (
    <Screen name="members">
      <PageHead title="Members">
        Everyone on the network, filterable by what they do and where they work. Connecting is not
        restricted by market — a builder in Mohali can connect into New York.
      </PageHead>

      <div className="filterbar">
        <span className="lbl">Role</span>
        {memberFilters.map((f) => (
          <Chip key={f.key} on={role === f.key} onClick={() => setRole(f.key)}>
            {f.label}
          </Chip>
        ))}
      </div>

      {state.status === 'loading' && <Loading label="Loading members…" />}
      {state.status === 'error' && <ErrorState error={state.error} onRetry={() => load(role)} />}

      {state.status === 'ready' && state.items.length === 0 && (
        <Empty title="No members match this filter">
          Try another role, or invite someone to the network.
        </Empty>
      )}

      {state.items.length > 0 && (
        <div className="mgrid">
          {state.items.map((m) => (
            <article className="card mcard" key={m.id}>
              <Avatar initials={m.initials} color={m.color} size="lg" />
              <h3>{m.name}</h3>
              <div className="role">{m.role} · {m.company}</div>
              <div className="loc">{m.location}</div>
              <div className="acts">
                <button
                  className="btn btn-dark btn-sm btn-block"
                  onClick={() => openModal('connect', { person: m })}
                >
                  Connect
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => navigate('/profile')}>
                  View
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </Screen>
  )
}
