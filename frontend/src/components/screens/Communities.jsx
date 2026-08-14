import { useCallback, useEffect, useRef, useState } from 'react'
import Screen, { PageHead } from '../layout/Screen'
import Chip from '../ui/Chip'
import Facepile from '../ui/Facepile'
import { Loading, Empty, ErrorState } from '../ui/States'
import { PlusIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import { listCommunities, joinCommunity, leaveCommunity, memberLabel } from '../../lib/communities'

const FILTERS = [
  { key: 'all', label: 'All', group: 'Type' },
  { key: 'region', label: 'By market', group: 'Type' },
  { key: 'industry', label: 'By asset class', group: 'Type' },
  { key: 'joined', label: 'Joined', group: 'Membership' },
]

function CommunityCard({ community, onOpen, onJoin, onLeave, busy }) {
  return (
    <article className="card ccard" onClick={onOpen}>
      <div className={`ccard-banner ${community.banner}`}>
        <span className="kind">{community.kind === 'region' ? 'MARKET' : 'ASSET CLASS'}</span>
      </div>
      <div className="ccard-body">
        <h3>{community.name}</h3>
        <div className="desc">{community.desc}</div>
        <div className="ccard-foot">
          <Facepile people={community.faces} />
          <span className="ccard-count">{memberLabel(community.memberCount)}</span>

          {community.joined ? (
            <button
              className="btn btn-ghost btn-sm ccard-join"
              data-busy={busy}
              onClick={(e) => { e.stopPropagation(); onLeave() }}
            >
              Joined
            </button>
          ) : community.pending ? (
            // Requested but not approved — offer to withdraw rather than re-request.
            <button
              className="btn btn-ghost btn-sm ccard-join"
              data-busy={busy}
              onClick={(e) => { e.stopPropagation(); onLeave() }}
              title="Awaiting an admin's approval"
            >
              Requested
            </button>
          ) : (
            <button
              className="btn btn-dark btn-sm ccard-join"
              data-busy={busy}
              onClick={(e) => { e.stopPropagation(); onJoin() }}
            >
              {community.joinPolicy === 'request' ? 'Request' : 'Join'}
            </button>
          )}
        </div>
      </div>
    </article>
  )
}

export default function Communities() {
  const { openModal } = useApp()
  const [filter, setFilter] = useState('all')
  // Guards against a slow earlier filter response landing after a newer one.
  const requestSeq = useRef(0)
  const [state, setState] = useState({ status: 'loading', items: [], error: null })
  const [busySlug, setBusySlug] = useState(null)
  const [notice, setNotice] = useState(null)

  const load = useCallback(async (which) => {
    const seq = ++requestSeq.current
    setState((s) => ({ ...s, status: 'loading' }))
    try {
      const page = await listCommunities({ filter: which })
      if (seq !== requestSeq.current) return // a newer filter already won
      setState({ status: 'ready', items: page.items, error: null })
    } catch (error) {
      if (seq !== requestSeq.current) return
      setState({ status: 'error', items: [], error })
    }
  }, [])

  useEffect(() => {
    load(filter)
  }, [filter, load])

  async function handleJoin(community) {
    setBusySlug(community.slug)
    setNotice(null)
    try {
      const result = await joinCommunity(community.slug)
      if (result.status === 'pending') {
        setNotice(`Your request to join ${community.name} is awaiting approval.`)
      }
      await load(filter)
    } catch (error) {
      setNotice(error.message)
    } finally {
      setBusySlug(null)
    }
  }

  async function handleLeave(community) {
    setBusySlug(community.slug)
    setNotice(null)
    try {
      await leaveCommunity(community.slug)
      await load(filter)
    } catch (error) {
      setNotice(error.message)
    } finally {
      setBusySlug(null)
    }
  }

  const typeFilters = FILTERS.filter((f) => f.group === 'Type')
  const membershipFilters = FILTERS.filter((f) => f.group === 'Membership')

  return (
    <Screen name="communities">
      <PageHead
        title="Communities"
        actions={
          <button
            className="btn btn-primary"
            onClick={() => openModal('create-community', { onCreated: () => load(filter) })}
          >
            <PlusIcon style={{ width: 15, height: 15 }} />
            Create community
          </button>
        }
      >
        Groups form around two things: the market you operate in, and the asset class you build or
        fund. Join as many as apply.
      </PageHead>

      <div className="filterbar">
        <span className="lbl">Type</span>
        {typeFilters.map((f) => (
          <Chip key={f.key} on={filter === f.key} onClick={() => setFilter(f.key)}>
            {f.label}
          </Chip>
        ))}
        <div className="filter-sep" />
        <span className="lbl">Membership</span>
        {membershipFilters.map((f) => (
          <Chip key={f.key} on={filter === f.key} onClick={() => setFilter(f.key)}>
            {f.label}
          </Chip>
        ))}
      </div>

      {notice && <div className="inline-error">{notice}</div>}

      {state.status === 'loading' && <Loading label="Loading communities…" />}

      {state.status === 'error' && (
        <ErrorState error={state.error} onRetry={() => load(filter)} />
      )}

      {state.status === 'ready' && state.items.length === 0 && (
        <Empty
          title={filter === 'joined' ? 'You have not joined any communities yet' : 'No communities found'}
          action={
            filter === 'joined' ? (
              <button className="btn btn-ghost btn-sm" onClick={() => setFilter('all')}>
                Browse all communities
              </button>
            ) : (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => openModal('create-community', { onCreated: () => load(filter) })}
              >
                Create the first one
              </button>
            )
          }
        >
          {filter === 'joined'
            ? 'Join a community and it will show up here.'
            : 'Nothing matches this filter yet.'}
        </Empty>
      )}

      {state.status === 'ready' && state.items.length > 0 && (
        <div className="cgrid">
          {state.items.map((c) => (
            <CommunityCard
              key={c.id}
              community={c}
              busy={busySlug === c.slug}
              onOpen={() =>
                openModal('community', { slug: c.slug, onChanged: () => load(filter) })
              }
              onJoin={() => handleJoin(c)}
              onLeave={() => handleLeave(c)}
            />
          ))}
        </div>
      )}
    </Screen>
  )
}
