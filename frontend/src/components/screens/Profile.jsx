import { useCallback, useEffect, useState } from 'react'
import Screen from '../layout/Screen'
import Avatar from '../ui/Avatar'
import { useApp } from '../../context/AppContext'
import {
  toDisplayUser, describeField, fetchMyStats, fetchMandate, fetchVisibility, setVisibility,
} from '../../lib/user'
import { visibilityFields, VISIBILITY_OPTIONS } from '../../data/profile'

export default function Profile() {
  const { user, openModal } = useApp()

  const [stats, setStats] = useState(null)
  const [mandate, setMandate] = useState(null)
  // field_key -> Public | Members | Private, as stored by the API.
  const [levels, setLevels] = useState({})
  const [busyField, setBusyField] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const [nextStats, nextMandate, rows] = await Promise.all([
        fetchMyStats(), fetchMandate(), fetchVisibility(),
      ])
      setStats(nextStats)
      setMandate(nextMandate)
      setLevels(Object.fromEntries(rows.map((r) => [r.field_key, r.level])))
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const currentUser = toDisplayUser(user, stats)

  /** Optimistic: the row moves at once and rolls back if the save fails. */
  async function chooseLevel(fieldKey, level) {
    if (levels[fieldKey] === level || busyField) return
    const previous = levels[fieldKey]
    setLevels((v) => ({ ...v, [fieldKey]: level }))
    setBusyField(fieldKey)
    setError(null)
    try {
      await setVisibility(fieldKey, level)
    } catch (err) {
      setLevels((v) => ({ ...v, [fieldKey]: previous }))
      setError(err.message)
    } finally {
      setBusyField(null)
    }
  }

  if (!currentUser) return null

  return (
    <Screen name="profile" narrow>
      <div className="pcover" />
      <div className="phead">
        <div className="phead-top">
          <Avatar initials={currentUser.initials} color={currentUser.color} size="xl" />
          <div className="who">
            <h1>{currentUser.name}</h1>
            <div className="rl">{currentUser.title} · {currentUser.company}</div>
            <div className="lc">{currentUser.location} · {currentUser.focus}</div>
          </div>
          <button
            className="btn btn-ghost"
            onClick={() =>
              openModal('edit-profile', { user, mandate, onSaved: (m) => setMandate(m) })
            }
          >
            Edit profile
          </button>
        </div>
        <div className="pstats">
          {currentUser.stats.map((s) => (
            <div className="pstat" key={s.l}>
              <div className="n">{s.n}</div>
              <div className="l">{s.l}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 22 }}>
        <div className="card pvis-card">
          <div className="pvis-head">
            <div style={{ flex: 1 }}>
              <h2>Field visibility</h2>
              <p>
                You decide what the public sees, what signed-in members see, and what stays private
                to you.
              </p>
            </div>
          </div>

          {error && <div className="inline-error">{error}</div>}

          {visibilityFields.map((f) => (
            <div className="vis-row" key={f.id}>
              <div className="info">
                <div className="k">{f.k}</div>
                <div className="v">{describeField(f.id, user, mandate)}</div>
              </div>
              <div className="vis-seg" data-busy={busyField === f.id}>
                {VISIBILITY_OPTIONS.map((opt) => (
                  <button
                    key={opt}
                    className={`vis-opt${levels[f.id] === opt ? ' on' : ''}`}
                    onClick={() => chooseLevel(f.id, opt)}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Screen>
  )
}
