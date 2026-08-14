import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Screen, { PageHead } from '../layout/Screen'
import Avatar from '../ui/Avatar'
import Tag from '../ui/Tag'
import { Loading, Empty, ErrorState } from '../ui/States'
import Composer from './Composer'
import { useApp } from '../../context/AppContext'
import { LikeIcon, CommentIcon, ShareIcon, DocumentIcon } from '../icons/Icons'
import { toDisplayUser } from '../../lib/user'
import { joinCommunity, memberLabel } from '../../lib/communities'
import {
  listFeed, toggleLike, listComments, addComment,
  myStats, suggestedCommunities, suggestedMembers,
  timeAgo, fileSize,
} from '../../lib/feed'

function Attachment({ file }) {
  if (file.kind === 'image') {
    return (
      <a className="post-image" href={file.url} target="_blank" rel="noreferrer">
        <img src={file.url} alt={file.name} loading="lazy" />
      </a>
    )
  }
  return (
    <a className="post-doc" href={file.url} target="_blank" rel="noreferrer" download={file.name}>
      <DocumentIcon />
      <div>
        <div className="n">{file.name}</div>
        <div className="s">{fileSize(file.sizeBytes)}</div>
      </div>
    </a>
  )
}

function Post({ post, onChanged }) {
  const [liked, setLiked] = useState(post.likedByMe)
  const [likeCount, setLikeCount] = useState(post.likeCount)
  const [showComments, setShowComments] = useState(false)
  const [comments, setComments] = useState([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [commentError, setCommentError] = useState(null)
  // Guards double-clicks: two toggles in flight can resolve out of order and
  // leave the row showing the opposite of the stored state.
  const liking = useRef(false)

  async function like() {
    if (liking.current) return
    liking.current = true

    // Optimistic — the count is cosmetic, and the server response corrects it.
    const next = !liked
    setLiked(next)
    setLikeCount((c) => c + (next ? 1 : -1))
    try {
      const result = await toggleLike(post.id)
      setLiked(result.liked)
      setLikeCount(result.like_count)
    } catch {
      setLiked(!next)
      setLikeCount((c) => c + (next ? -1 : 1))
    } finally {
      liking.current = false
    }
  }

  async function openComments() {
    const next = !showComments
    setShowComments(next)
    if (next && comments.length === 0) {
      try {
        setComments(await listComments(post.id))
      } catch {
        setComments([])
      }
    }
  }

  async function postComment() {
    const body = draft.trim()
    if (!body) return
    setBusy(true)
    setCommentError(null)
    try {
      const created = await addComment(post.id, body)
      setComments((c) => [...c, created])
      setDraft('')
      onChanged?.()
    } catch (err) {
      setCommentError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const sub = [post.author.company, post.author.location].filter(Boolean).join(' · ')

  return (
    <article className="card post">
      <div className="post-head">
        <Avatar initials={post.author.initials} color={post.author.color} />
        <div className="post-meta">
          <div className="post-name">{post.author.name}</div>
          <div className="post-sub">
            {sub}
            {post.community && <> · posted in <b>{post.community.name}</b></>}
            {' · '}{timeAgo(post.createdAt)}
          </div>
        </div>
        {post.community && <Tag variant="shared">Community post</Tag>}
      </div>

      {post.body?.trim() && <div className="post-body">{post.body}</div>}

      {post.attachments.length > 0 && (
        <div className="post-files">
          {post.attachments.map((f) => <Attachment key={f.id} file={f} />)}
        </div>
      )}

      {post.embed && (
        <div className="post-embed">
          <div className="post-embed-t">{post.embed.title}</div>
          {post.embed.detail && <div className="post-embed-d">{post.embed.detail}</div>}
        </div>
      )}

      <div className="post-stats">
        <button className={`post-act${liked ? ' liked' : ''}`} onClick={like}>
          <LikeIcon />{likeCount}
        </button>
        <button className="post-act" onClick={openComments}>
          <CommentIcon />
          {(() => {
            const n = Math.max(post.commentCount, comments.length)
            return `${n} ${n === 1 ? 'comment' : 'comments'}`
          })()}
        </button>
        <button className="post-act"><ShareIcon />Share</button>
      </div>

      {showComments && (
        <div className="post-comments">
          {comments.map((c) => (
            <div className="post-comment" key={c.id}>
              <Avatar initials={c.author.initials} color={c.author.avatar_color} size="sm" />
              <div>
                <div className="n">{c.author.name} <span>{timeAgo(c.created_at)}</span></div>
                <div className="b">{c.body}</div>
              </div>
            </div>
          ))}
          {commentError && <div className="inline-error">{commentError}</div>}
          <div className="post-comment-new">
            <input
              placeholder="Add a comment…"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && postComment()}
            />
            <button
              className="btn btn-dark btn-sm"
              onClick={postComment}
              disabled={!draft.trim()}
              data-busy={busy}
            >
              Reply
            </button>
          </div>
        </div>
      )}
    </article>
  )
}

export default function Home() {
  const navigate = useNavigate()
  const { openModal, user } = useApp()
  const currentUser = toDisplayUser(user)

  const [feed, setFeed] = useState({ status: 'loading', items: [], error: null })
  const [stats, setStats] = useState(null)
  const [communities, setCommunities] = useState([])
  const [people, setPeople] = useState([])
  const [railsState, setRailsState] = useState('loading')
  const [joining, setJoining] = useState(null)
  const [railError, setRailError] = useState(null)

  const feedSeq = useRef(0)

  const loadFeed = useCallback(async () => {
    const seq = ++feedSeq.current
    setFeed((f) => ({ ...f, status: f.items.length ? f.status : 'loading' }))
    try {
      const page = await listFeed()
      if (seq !== feedSeq.current) return
      setFeed({ status: 'ready', items: page.items, error: null })
    } catch (error) {
      if (seq !== feedSeq.current) return
      // Keep what is already on screen — a failed background refresh should not
      // wipe a feed the member is reading.
      setFeed((f) =>
        f.items.length ? { ...f, status: 'ready' } : { status: 'error', items: [], error },
      )
    }
  }, [])

  const loadRails = useCallback(async () => {
    setRailsState('loading')
    const [s, c, p] = await Promise.all([
      myStats().catch(() => null),
      suggestedCommunities().catch(() => null),
      suggestedMembers().catch(() => null),
    ])
    setStats(s)
    setCommunities(c ?? [])
    setPeople(p ?? [])
    // Only claim "nothing to suggest" when the call actually succeeded.
    setRailsState(c === null || p === null ? 'error' : 'ready')
  }, [])

  useEffect(() => {
    loadFeed()
    loadRails()
  }, [loadFeed, loadRails])

  async function join(community) {
    setJoining(community.slug)
    try {
      await joinCommunity(community.slug)
      await Promise.all([loadRails(), loadFeed()])
    } catch (error) {
      setRailError(error.message)
    } finally {
      setJoining(null)
    }
  }

  return (
    <Screen name="home">
      <PageHead title="Home">
        What the people and communities you follow are working on.
      </PageHead>

      <div className="feed-grid">
        <div>
          <Composer
            currentUser={currentUser}
            onPosted={() => { loadFeed(); loadRails() }}
          />

          {feed.status === 'loading' && <Loading label="Loading your feed…" />}

          {feed.status === 'error' && <ErrorState error={feed.error} onRetry={loadFeed} />}

          {feed.status === 'ready' && feed.items.length === 0 && (
            <Empty
              title="Your feed is empty"
              action={
                <button className="btn btn-dark btn-sm" onClick={() => navigate('/communities')}>
                  Find communities
                </button>
              }
            >
              Post an update above, or join a community to see what its members are working on.
            </Empty>
          )}

          {feed.items.map((post) => (
            <Post key={post.id} post={post} onChanged={loadFeed} />
          ))}
        </div>

        <aside className="feed-rail">
          <div className="card rail-card">
            <h3>Your network</h3>
            <div className="rail-stat">
              <span className="l">Connections</span>
              <span className="v">{stats?.connections ?? '—'}</span>
            </div>
            <div className="rail-stat">
              <span className="l">Communities</span>
              <span className="v">{stats?.communities ?? '—'}</span>
            </div>
            <div className="rail-stat">
              <span className="l">Profile views · 30d</span>
              <span className="v">{stats?.profile_views ?? '—'}</span>
            </div>
          </div>

          <div className="card rail-card">
            <h3>Communities to join</h3>
            {railError && <div className="inline-error">{railError}</div>}
            {railsState === 'loading' ? (
              <p className="cm-hint">Loading…</p>
            ) : railsState === 'error' ? (
              <p className="cm-hint">Could not load suggestions.</p>
            ) : communities.length === 0 ? (
              <p className="cm-hint">You have joined everything on offer.</p>
            ) : (
              communities.map((c) => (
                <div className="rail-item" key={c.id}>
                  <Avatar initials={c.initials} color={c.banner.replace('b', 'a')} size="sm" />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="t">{c.name}</div>
                    <div className="s">{memberLabel(c.member_count)}</div>
                  </div>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => join(c)}
                    data-busy={joining === c.slug}
                  >
                    {c.join_policy === 'request' ? 'Request' : 'Join'}
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="card rail-card">
            <h3>People you may know</h3>
            {railsState === 'loading' ? (
              <p className="cm-hint">Loading…</p>
            ) : railsState === 'error' ? (
              <p className="cm-hint">Could not load suggestions.</p>
            ) : people.length === 0 ? (
              <p className="cm-hint">No suggestions right now.</p>
            ) : (
              people.map((p) => (
                <div className="rail-item" key={p.id}>
                  <Avatar initials={p.initials} color={p.avatar_color} size="sm" />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="t">{p.name}</div>
                    <div className="s">
                      {[p.company, p.location].filter(Boolean).join(' · ') || 'Member'}
                    </div>
                  </div>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() =>
                      openModal('connect', {
                        person: {
                          id: p.id,
                          name: p.name,
                          initials: p.initials,
                          color: p.avatar_color,
                          company: p.company || '—',
                          location: p.location || '—',
                          role: p.role || 'Member',
                        },
                        onSent: loadRails,
                      })
                    }
                  >
                    Connect
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </Screen>
  )
}
