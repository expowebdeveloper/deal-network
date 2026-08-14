import { useCallback, useEffect, useState } from 'react'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import Avatar from '../ui/Avatar'
import Tag from '../ui/Tag'
import Facepile from '../ui/Facepile'
import { Loading, ErrorState } from '../ui/States'
import { useApp } from '../../context/AppContext'
import {
  getCommunity, joinCommunity, leaveCommunity, listCommunityMembers,
  listCommunityPosts, createCommunityPost, memberLabel,
} from '../../lib/communities'

const TABS = ['Discussion', 'Channels', 'Members']

function timeAgo(iso) {
  const seconds = Math.max(1, (Date.now() - new Date(iso).getTime()) / 1000)
  const steps = [
    [60, 's'], [3600, 'm'], [86400, 'h'], [604800, 'd'],
  ]
  if (seconds < 60) return 'just now'
  for (let i = 1; i < steps.length; i += 1) {
    if (seconds < steps[i][0]) return `${Math.floor(seconds / steps[i - 1][0])}${steps[i][1]}`
  }
  return `${Math.floor(seconds / 604800)}w`
}

export default function CommunityModal({ slug, onChanged }) {
  const { closeModal } = useApp()
  const [tab, setTab] = useState('Discussion')

  const [community, setCommunity] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  const [posts, setPosts] = useState([])
  // The discussion is members-only; the API returns 403 to everyone else.
  const [postsLocked, setPostsLocked] = useState(false)
  const [members, setMembers] = useState([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      const detail = await getCommunity(slug)
      setCommunity(detail)
      setStatus('ready')

      // Secondary data — a failure here should not blank the modal.
      listCommunityPosts(detail.id)
        .then((p) => { setPosts(p.items); setPostsLocked(false) })
        .catch((e) => { setPosts([]); setPostsLocked(e?.status === 403) })
      listCommunityMembers(slug).then((m) => setMembers(m.items)).catch(() => setMembers([]))
    } catch (err) {
      setError(err)
      setStatus('error')
    }
  }, [slug])

  useEffect(() => { load() }, [load])

  async function toggleMembership() {
    setBusy(true)
    setNotice(null)
    try {
      if (community.joined) {
        await leaveCommunity(slug)
      } else {
        const result = await joinCommunity(slug)
        if (result.status === 'pending') {
          setNotice('Your request is awaiting an admin’s approval.')
        }
      }
      await load()
      onChanged?.()
    } catch (err) {
      setNotice(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function post() {
    const body = draft.trim()
    if (!body) return
    setBusy(true)
    setNotice(null)
    try {
      await createCommunityPost(community.id, body)
      setDraft('')
      const fresh = await listCommunityPosts(community.id)
      setPosts(fresh.items)
    } catch (err) {
      setNotice(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (status === 'loading') {
    return (
      <Modal width="wide">
        <ModalBody><Loading label="Loading community…" /></ModalBody>
      </Modal>
    )
  }

  if (status === 'error') {
    return (
      <Modal width="wide">
        <ModalBody><ErrorState error={error} onRetry={load} /></ModalBody>
        <ModalFoot>
          <button className="btn btn-ghost" onClick={closeModal}>Close</button>
        </ModalFoot>
      </Modal>
    )
  }

  return (
    <Modal width="wide">
      <div className={`ccard-banner ${community.banner} cm-banner`}>
        <span className="kind">{community.kind === 'region' ? 'MARKET' : 'ASSET CLASS'}</span>
      </div>

      <ModalHead className="cm-head">
        <Avatar
          initials={community.initials}
          color={community.banner.replace('b', 'a')}
          size="lg"
        />
        <ModalTitle
          title={community.name}
          sub={`${community.location} · ${memberLabel(community.memberCount)} · ${
            community.joinPolicy === 'open'
              ? 'Open to all members'
              : community.joinPolicy === 'request'
                ? 'Request to join'
                : 'Invite only'
          }`}
        />
        {community.joined ? (
          <button className="btn btn-ghost" onClick={toggleMembership} data-busy={busy}>
            Leave
          </button>
        ) : (
          <button className="btn btn-primary" onClick={toggleMembership} data-busy={busy}>
            {community.joinPolicy === 'request' ? 'Request to join' : 'Join community'}
          </button>
        )}
      </ModalHead>

      <ModalBody className="cm-body">
        {notice && <div className="inline-error">{notice}</div>}

        <div className="tabs" style={{ marginBottom: 16 }}>
          {TABS.map((t) => (
            <button key={t} className={`tab${tab === t ? ' on' : ''}`} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </div>

        {tab === 'Discussion' && (
          <div className="cm-layout">
            <div>
              {community.joined && (
                <div className="card cm-post cm-composer">
                  <textarea
                    placeholder={`Post to ${community.name}…`}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    rows={2}
                  />
                  <div className="cm-composer-foot">
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={post}
                      disabled={!draft.trim()}
                      data-busy={busy}
                    >
                      Post
                    </button>
                  </div>
                </div>
              )}

              {posts.length === 0 ? (
                <p className="cm-hint">
                  {postsLocked
                    ? 'The discussion is members only — join to read it.'
                    : community.joined
                      ? 'No posts yet — start the conversation.'
                      : 'No posts yet.'}
                </p>
              ) : (
                posts.map((p) => (
                  <div className="card cm-post" key={p.id}>
                    <div className="post-head">
                      <Avatar
                        initials={p.author.initials}
                        color={p.author.avatar_color}
                        size="sm"
                      />
                      <div className="post-meta">
                        <div className="post-name">{p.author.name}</div>
                        <div className="post-sub">
                          {[p.author.company, timeAgo(p.created_at)].filter(Boolean).join(' · ')}
                        </div>
                      </div>
                    </div>
                    <div className="post-body">{p.body}</div>
                  </div>
                ))
              )}
            </div>

            <div>
              <div className="sec-title" style={{ marginBottom: 9 }}>Channels</div>
              <div className="cm-channels">
                {community.channels.length
                  ? community.channels.map((c) => <div key={c}>{c}</div>)
                  : <div className="cm-hint">No channels yet</div>}
              </div>
              <div className="sec-title" style={{ margin: '16px 0 9px' }}>Members</div>
              {/* The public facepile — the full roster is members-only. */}
              <Facepile people={(members.length ? members : community.faces).slice(0, 6)} />
            </div>
          </div>
        )}

        {tab === 'Channels' && (
          <div className="cm-channels">
            {community.channels.length
              ? community.channels.map((c) => <div key={c}>{c}</div>)
              : <p className="cm-hint">No channels yet.</p>}
          </div>
        )}

        {tab === 'Members' && (
          members.length === 0 ? (
            <p className="cm-hint">No members yet.</p>
          ) : (
            <div className="cm-members">
              {members.map((m) => (
                <div className="cm-member" key={m.id}>
                  <Avatar initials={m.initials} color={m.color} size="sm" />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="t">{m.name}</div>
                    <div className="s">{[m.role, m.company].filter(Boolean).join(' · ')}</div>
                  </div>
                  {m.isAdmin && <Tag variant="gold">Admin</Tag>}
                </div>
              ))}
            </div>
          )
        )}
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal}>Close</button>
      </ModalFoot>
    </Modal>
  )
}
