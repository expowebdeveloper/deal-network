import { useCallback, useEffect, useRef, useState } from 'react'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import Avatar from '../ui/Avatar'
import Tag from '../ui/Tag'
import Facepile from '../ui/Facepile'
import CommunityMenu from '../ui/CommunityMenu'
import { Loading, ErrorState } from '../ui/States'
import { PhotoIcon, VideoIcon, DocumentIcon, CloseIcon, SettingsIcon, CameraIcon } from '../icons/Icons'
import { ACCEPT, uploadMedia, deleteMedia, fileSize } from '../../lib/feed'
import { useApp } from '../../context/AppContext'
import GroupPhotoModal from './GroupPhotoModal'
import {
  getCommunity, joinCommunity, leaveCommunity, listCommunityMembers,
  listCommunityPosts, createCommunityPost, memberLabel,
  assignableRoles, canManageMember, canManageRoles, changeMemberRole,
  roleErrorMessage, roleLabel,
  POST_POLICIES, canPostIn, postRefusalMessage, setPostPolicy,
  ACCESS_MODES, INVITE_POLICIES, accessModeOf, communityErrorMessage,
  isDraft, publishCommunity, setAccessMode, setInvitePolicy,
  renameCommunity, setCommunityLogo, removeMember,
} from '../../lib/communities'

import MediaViewer from '../media/MediaViewer'

const TABS = ['Discussion', 'Channels', 'Members']

// Plain members wear no badge — every row would carry one and it would stop
// meaning anything. Only standing above ordinary membership is worth showing.
const ROLE_TAG = { owner: 'gold', admin: 'internal', moderator: 'shared' }

function RoleBadge({ role }) {
  const variant = ROLE_TAG[role]
  if (!variant) return null
  return <Tag variant={variant}>{roleLabel(role)}</Tag>
}

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

export default function CommunityModal({ slug, initialTab = 'Discussion', onChanged }) {
  const { closeModal, openModal } = useApp()
  // Renaming regenerates the slug server-side, so the one this modal was opened
  // with goes stale the moment an admin edits the name. Every request below
  // uses this instead of the prop, and the rename handler moves it forward.
  const [activeSlug, setActiveSlug] = useState(slug)
  useEffect(() => { setActiveSlug(slug) }, [slug])
  const [tab, setTab] = useState(initialTab)
  useEffect(() => { if (initialTab) setTab(initialTab) }, [initialTab])

  const [community, setCommunity] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  const [posts, setPosts] = useState([])
  // The discussion is members-only; the API returns 403 to everyone else.
  const [postsLocked, setPostsLocked] = useState(false)
  const [members, setMembers] = useState([])
  const [draft, setDraft] = useState('')
  const [attachments, setAttachments] = useState([])
  // A counter rather than a flag: two pickers can be uploading at once, and a
  // boolean would unlock Post while the second batch was still running.
  const [uploads, setUploads] = useState(0)
  const photoInput = useRef(null)
  const videoInput = useRef(null)
  const docInput = useRef(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  // Role changes report separately from the join/leave notice: they happen on
  // the Members tab and the reply — usually an upgrade prompt — belongs there.
  const [roleBusyId, setRoleBusyId] = useState(null)
  const [roleNotice, setRoleNotice] = useState(null)
  const [savingPolicy, setSavingPolicy] = useState(false)
  const [policyNotice, setPolicyNotice] = useState(null)
  // Each settings control reports separately, so saving one does not wipe the
  // confirmation still on screen from another.
  const [savingAccess, setSavingAccess] = useState(false)
  const [accessNotice, setAccessNotice] = useState(null)
  const [savingInvite, setSavingInvite] = useState(false)
  const [inviteNotice, setInviteNotice] = useState(null)
  const [publishing, setPublishing] = useState(false)
  const [publishError, setPublishError] = useState(null)
  // Identity: the name is a form (typed, then submitted), the picture is not.
  const [nameDraft, setNameDraft] = useState('')
  const [savingName, setSavingName] = useState(false)
  const [nameNotice, setNameNotice] = useState(null)
  const [savingLogo, setSavingLogo] = useState(false)
  const [logoNotice, setLogoNotice] = useState(null)
  const [showPhotoModal, setShowPhotoModal] = useState(false)
  const logoInput = useRef(null)
  const [removingId, setRemovingId] = useState(null)
  // The row currently asking "are you sure?" — see handleRemoveMember.
  const [confirmRemoveId, setConfirmRemoveId] = useState(null)

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      const detail = await getCommunity(activeSlug)
      setCommunity(detail)
      setNameDraft(detail.name)
      setStatus('ready')

      // Secondary data — a failure here should not blank the modal.
      listCommunityPosts(detail.id)
        .then((p) => { setPosts(p.items); setPostsLocked(false) })
        .catch((e) => { setPosts([]); setPostsLocked(e?.status === 403) })
      listCommunityMembers(activeSlug).then((m) => setMembers(m.items)).catch(() => setMembers([]))
    } catch (err) {
      setError(err)
      setStatus('error')
    }
  }, [activeSlug])

  useEffect(() => { load() }, [load])

  async function join() {
    setBusy(true)
    setNotice(null)
    try {
      const result = await joinCommunity(activeSlug)
      if (result.status === 'pending') {
        setNotice('Your request is awaiting an admin’s approval.')
      }
      await load()
      onChanged?.()
    } catch (err) {
      setNotice(err.message)
    } finally {
      setBusy(false)
    }
  }

  /**
   * Leaving asks first.
   *
   * The confirm replaces this modal, since the app renders one at a time — so
   * cancelling reopens the community on the tab the member was already on, and
   * confirming closes out to the list. The refusal for an owner surfaces inside
   * the confirm rather than here, which is why nothing is caught.
   */
  function requestLeave() {
    openModal('confirm', {
      title: `Leave ${community.name}?`,
      message: 'You will lose access to its discussion and members. '
        + `Rejoining is ${community.joinPolicy === 'open'
          ? 'one click away.'
          : 'subject to approval again.'}`,
      confirmLabel: 'Leave community',
      tone: 'danger',
      onConfirm: async () => {
        await leaveCommunity(activeSlug)
        onChanged?.()
      },
      onCancel: () => openModal('community', { slug: activeSlug, onChanged }),
    })
  }

  async function handleFiles(event) {
    const files = [...event.target.files]
    event.target.value = '' // let the same file be chosen again
    if (!files.length) return

    setUploads((n) => n + 1)
    setNotice(null)
    const problems = []
    for (const file of files) {
      try {
        const media = await uploadMedia(file)
        setAttachments((current) => [...current, media])
      } catch (err) {
        // One refused file should not throw away the rest of the batch — an
        // over-size video alongside two fine images is the common case.
        problems.push(`${file.name}: ${err.message}`)
      }
    }
    if (problems.length) setNotice(problems.join(' · '))
    setUploads((n) => Math.max(0, n - 1))
  }

  function removeAttachment(media) {
    setAttachments((current) => current.filter((a) => a.id !== media.id))
    // Nothing references it yet, so take it out of storage rather than orphan it.
    deleteMedia(media.id).catch(() => {})
  }

  async function post() {
    const body = draft.trim()
    if (!body && attachments.length === 0) return
    setBusy(true)
    setNotice(null)
    try {
      await createCommunityPost(community.id, body, attachments.map((a) => a.id))
      setDraft('')
      setAttachments([]) // the post owns them now — do not delete
      const fresh = await listCommunityPosts(community.id)
      setPosts(fresh.items)
    } catch (err) {
      setNotice(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleRoleChange(member, nextRole) {
    if (nextRole === member.communityRole) return
    setRoleBusyId(member.userId)
    setRoleNotice(null)
    try {
      const updated = await changeMemberRole(community.id, member.userId, nextRole)
      const applied = updated.communityRole || nextRole
      setMembers((rows) => rows.map((r) => (
        r.userId === member.userId ? { ...r, communityRole: applied } : r
      )))
      setRoleNotice({ tone: 'ok', text: `${member.name} is now ${roleLabel(applied)}.` })
      onChanged?.()
    } catch (err) {
      // The plan ceilings live on the server, so the refusal is what tells us a
      // moderator is out of reach — the option is offered either way.
      setRoleNotice({ tone: 'error', text: roleErrorMessage(err, nextRole) })
    } finally {
      setRoleBusyId(null)
    }
  }

  async function handlePostPolicy(next) {
    if (next === community.postMinRole) return
    setSavingPolicy(true)
    setPolicyNotice(null)
    try {
      const updated = await setPostPolicy(activeSlug, next)
      // Merge the one field rather than replacing the object: the PATCH reply
      // is a fresh community and would otherwise clobber nothing important
      // today, but this keeps the modal's state owned in one place.
      setCommunity((c) => ({ ...c, postMinRole: updated.postMinRole }))
      setPolicyNotice({
        tone: 'ok',
        text: `Saved. ${POST_POLICIES.find((p) => p.key === next)?.label} can post.`,
      })
      onChanged?.()
    } catch (err) {
      setPolicyNotice({ tone: 'error', text: err.message })
    } finally {
      setSavingPolicy(false)
    }
  }

  async function handleRename(event) {
    event.preventDefault()
    const next = nameDraft.trim()
    if (!next || next === community.name) return
    setSavingName(true)
    setNameNotice(null)
    try {
      const updated = await renameCommunity(activeSlug, next)
      // The slug is derived from the name, so it has just changed underneath
      // us. Adopt the new one before anything else in this modal uses it.
      setActiveSlug(updated.slug)
      setCommunity((c) => ({
        ...c, name: updated.name, slug: updated.slug, initials: updated.initials,
      }))
      setNameDraft(updated.name)
      setNameNotice({ tone: 'ok', text: 'Saved.' })
      onChanged?.()
    } catch (err) {
      setNameNotice({
        tone: 'error',
        text: communityErrorMessage(err, 'Could not rename the community.'),
      })
    } finally {
      setSavingName(false)
    }
  }

  async function handleLogo(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setSavingLogo(true)
    setLogoNotice(null)
    try {
      const media = await uploadMedia(file)
      // `path` and not `url`: the value is stored on the community row, so it
      // must not carry this client's API origin.
      const updated = await setCommunityLogo(activeSlug, media.path)
      setCommunity((c) => ({ ...c, logoUrl: updated.logoUrl }))
      setLogoNotice({ tone: 'ok', text: 'Picture updated.' })
      onChanged?.()
    } catch (err) {
      setLogoNotice({ tone: 'error', text: err.message })
    } finally {
      setSavingLogo(false)
    }
  }

  async function handleRemoveLogo() {
    setSavingLogo(true)
    setLogoNotice(null)
    try {
      const updated = await setCommunityLogo(activeSlug, null)
      setCommunity((c) => ({ ...c, logoUrl: updated.logoUrl }))
      setLogoNotice({ tone: 'ok', text: 'Back to the initials.' })
      onChanged?.()
    } catch (err) {
      setLogoNotice({ tone: 'error', text: err.message })
    } finally {
      setSavingLogo(false)
    }
  }

  /**
   * Remove a member, confirmed on the row itself.
   *
   * Deliberately not the confirm modal: the app shows one modal at a time, so
   * confirming there would close this one and drop the admin out of the
   * community they are in the middle of administering. A row action should
   * leave them where they are.
   */
  async function handleRemoveMember(member) {
    if (confirmRemoveId !== member.userId) {
      setConfirmRemoveId(member.userId)
      return
    }
    setRemovingId(member.userId)
    setRoleNotice(null)
    try {
      await removeMember(community.id, member.userId)
      setMembers((rows) => rows.filter((m) => m.userId !== member.userId))
      setCommunity((c) => ({
        ...c, memberCount: Math.max(0, (c.memberCount || 1) - 1),
      }))
      setRoleNotice({ tone: 'ok', text: `${member.name} was removed.` })
      onChanged?.()
    } catch (err) {
      setRoleNotice({
        tone: 'error',
        text: communityErrorMessage(err, 'Could not remove that member.'),
      })
    } finally {
      setRemovingId(null)
      setConfirmRemoveId(null)
    }
  }

  async function handlePublish() {
    setPublishing(true)
    setPublishError(null)
    try {
      const updated = await publishCommunity(activeSlug)
      setCommunity((c) => ({
        ...c, status: updated.status, publishedAt: updated.publishedAt,
      }))
      onChanged?.()
    } catch (err) {
      setPublishError(communityErrorMessage(err, 'Could not publish the community.'))
    } finally {
      setPublishing(false)
    }
  }

  async function handleAccessMode(next) {
    if (next === accessModeOf(community)) return
    setSavingAccess(true)
    setAccessNotice(null)
    try {
      const updated = await setAccessMode(activeSlug, next)
      setCommunity((c) => ({
        ...c, visibility: updated.visibility, joinPolicy: updated.joinPolicy,
      }))
      setAccessNotice({
        tone: 'ok',
        text: `Saved. ${ACCESS_MODES.find((m) => m.key === next)?.label}.`,
      })
      onChanged?.()
    } catch (err) {
      // Private, approval and invite joining are each gated by the plan, so the
      // refusal here is usually an upgrade prompt rather than a validation error.
      setAccessNotice({
        tone: 'error',
        text: communityErrorMessage(err, 'Could not change who can join.'),
      })
    } finally {
      setSavingAccess(false)
    }
  }

  async function handleInvitePolicy(next) {
    if (next === community.inviteMinRole) return
    setSavingInvite(true)
    setInviteNotice(null)
    try {
      const updated = await setInvitePolicy(activeSlug, next)
      setCommunity((c) => ({ ...c, inviteMinRole: updated.inviteMinRole }))
      setInviteNotice({
        tone: 'ok',
        text: `Saved. ${INVITE_POLICIES.find((p) => p.key === next)?.label} can invite.`,
      })
      onChanged?.()
    } catch (err) {
      setInviteNotice({
        tone: 'error',
        text: communityErrorMessage(err, 'Could not change who can invite.'),
      })
    } finally {
      setSavingInvite(false)
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
        <div
          className="wa-avatar-wrap"
          style={{ width: 64, height: 64, border: '2px solid var(--surface)' }}
          onClick={() => setShowPhotoModal(true)}
          title="Click to view group photo"
        >
          <Avatar
            initials={community.initials}
            color={community.banner.replace('b', 'a')}
            size="lg"
            src={community.logoUrl}
            alt={`${community.name} logo`}
          />
          <div className="wa-avatar-overlay">
            <CameraIcon style={{ width: 18, height: 18 }} />
            <span className="wa-avatar-overlay-text" style={{ fontSize: 8 }}>View</span>
          </div>
        </div>
        <ModalTitle
          title={community.name}
          sub={`${community.location} · ${memberLabel(community.memberCount)} · ${
            isDraft(community)
              ? 'Draft — not published'
              : community.visibility === 'Private'
                ? 'Private · invite only'
                : community.joinPolicy === 'open'
                  ? 'Open to all members'
                  : community.joinPolicy === 'request'
                    ? 'Request to join'
                    : 'Invite only'
          }`}
        />
        <div className="cm-head-actions">
          {isDraft(community) ? (
            canManageRoles(community.myRole) ? (
              <button
                className="btn btn-primary"
                onClick={handlePublish}
                data-busy={publishing}
                disabled={publishing}
              >
                {publishing ? 'Publishing…' : 'Publish'}
              </button>
            ) : null
          ) : community.joined ? (
            <button className="btn btn-ghost" onClick={requestLeave} data-busy={busy}>
              Leave
            </button>
          ) : (
            <button className="btn btn-primary" onClick={join} data-busy={busy}>
              {community.joinPolicy === 'request' ? 'Request to join' : 'Join community'}
            </button>
          )}

          <CommunityMenu
            community={community}
            onOpenSettings={() => openModal('community-settings', { slug: activeSlug, onChanged: load })}
            onOpenTab={(targetTab) => setTab(targetTab)}
            onJoin={join}
            onLeave={requestLeave}
            busy={busy}
            variant="header"
            align="right"
          />
        </div>
      </ModalHead>

      <ModalBody className="cm-body">
        {notice && <div className="inline-error">{notice}</div>}

        {isDraft(community) && (
          <div className="cm-draft">
            <div>
              <span className="t">This community is a draft</span>
              <span className="s">
                Only you can see it. Set it up below, then publish it — that is when
                it appears for other members and people can join.
              </span>
            </div>
            {canManageRoles(community.myRole) && (
              <button
                className="btn btn-primary"
                onClick={handlePublish}
                data-busy={publishing}
                disabled={publishing}
              >
                {publishing ? 'Publishing…' : 'Publish'}
              </button>
            )}
          </div>
        )}
        {publishError && <div className="inline-error">{publishError}</div>}

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
              {community.joined && !canPostIn(community) && (
                // Saying so here beats letting them write a post and refusing
                // it on submit. The API enforces the same rule with the same
                // sentence, so a stale tab gets the identical answer.
                <div className="cm-locked">{postRefusalMessage(community)}</div>
              )}

              {community.joined && canPostIn(community) && (
                <div className="card cm-post cm-composer">
                  <textarea
                    placeholder={`Post to ${community.name}…`}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    rows={2}
                  />
                  {attachments.length > 0 && (
                    <div className="composer-files">
                      {attachments.map((a) => (
                        <div
                          className={`composer-file${
                            a.kind === 'image' || a.kind === 'video' ? ' is-image' : ''}`}
                          key={a.id}
                        >
                          {a.kind === 'image' ? (
                            <img src={a.url} alt={a.name} />
                          ) : a.kind === 'video' ? (
                            <video src={a.url} muted playsInline preload="metadata" />
                          ) : (
                            <div className="composer-file-doc">
                              <DocumentIcon />
                              <div>
                                <div className="n">{a.name}</div>
                                <div className="s">{fileSize(a.sizeBytes)}</div>
                              </div>
                            </div>
                          )}
                          <button
                            className="composer-file-remove"
                            onClick={() => removeAttachment(a)}
                            aria-label={`Remove ${a.name}`}
                          >
                            <CloseIcon />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="cm-composer-foot">
                    <div className="cm-composer-acts">
                      <button
                        className="composer-act"
                        onClick={() => photoInput.current?.click()}
                      >
                        <PhotoIcon />Photo
                      </button>
                      <button
                        className="composer-act"
                        onClick={() => videoInput.current?.click()}
                      >
                        <VideoIcon />Video
                      </button>
                      <button
                        className="composer-act"
                        onClick={() => docInput.current?.click()}
                      >
                        <DocumentIcon />Document
                      </button>
                    </div>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={post}
                      disabled={(!draft.trim() && attachments.length === 0) || uploads > 0}
                      data-busy={busy}
                    >
                      {uploads > 0 ? 'Uploading…' : 'Post'}
                    </button>
                  </div>

                  <input
                    ref={photoInput}
                    type="file"
                    accept={ACCEPT.image}
                    multiple
                    hidden
                    onChange={handleFiles}
                  />
                  <input
                    ref={videoInput}
                    type="file"
                    accept={ACCEPT.video}
                    multiple
                    hidden
                    onChange={handleFiles}
                  />
                  <input
                    ref={docInput}
                    type="file"
                    accept={ACCEPT.document}
                    multiple
                    hidden
                    onChange={handleFiles}
                  />
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
                        color={p.author.color || p.author.avatar_color}
                        size="sm"
                      />
                      <div className="post-meta">
                        <div className="post-name">{p.author.name}</div>
                        <div className="post-sub">
                          {[p.author.company, timeAgo(p.createdAt || p.created_at)].filter(Boolean).join(' · ')}
                        </div>
                      </div>
                    </div>
                    {p.body?.trim() && <div className="post-body">{p.body}</div>}
                    <MediaViewer files={p.attachments} />
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

        {tab === 'Settings' && (
          <div className="cm-settings">
            <div className="sec-title" style={{ marginBottom: 6 }}>
              Name and picture
            </div>
            <p className="cm-hint" style={{ marginTop: 0 }}>
              Renaming changes the community&rsquo;s address too, so old links to it
              stop working.
            </p>

            {nameNotice && (
              <div className={nameNotice.tone === 'error' ? 'inline-error' : 'cm-role-ok'}>
                {nameNotice.text}
              </div>
            )}
            {logoNotice && (
              <div className={logoNotice.tone === 'error' ? 'inline-error' : 'cm-role-ok'}>
                {logoNotice.text}
              </div>
            )}

            <div className="cm-identity">
              <div className="cm-identity-pic">
                <div
                  className="wa-avatar-wrap"
                  onClick={() => setShowPhotoModal(true)}
                  title="Click to view or change group profile photo"
                >
                  <Avatar
                    initials={community.initials}
                    color={community.banner.replace('b', 'a')}
                    size="lg"
                    src={community.logoUrl}
                    alt={`${community.name} logo`}
                  />
                  <div className="wa-avatar-overlay">
                    <CameraIcon />
                    <span className="wa-avatar-overlay-text">
                      {community.logoUrl ? 'Change photo' : 'Add photo'}
                    </span>
                  </div>
                </div>
                <div className="cm-identity-pic-actions" style={{ marginTop: 6, alignItems: 'center' }}>
                  <input
                    ref={logoInput}
                    type="file"
                    accept={ACCEPT.image}
                    className="hidden"
                    onChange={handleLogo}
                  />
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', justifyContent: 'center' }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setShowPhotoModal(true)}
                    >
                      View photo
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => logoInput.current?.click()}
                      data-busy={savingLogo}
                      disabled={savingLogo}
                    >
                      {community.logoUrl ? 'Change' : 'Upload'}
                    </button>
                    {community.logoUrl && (
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={handleRemoveLogo}
                        disabled={savingLogo}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              </div>

              <form className="cm-identity-name" onSubmit={handleRename}>
                <label htmlFor="community-name">Community name</label>
                <div className="cm-identity-row">
                  <input
                    id="community-name"
                    className="input"
                    value={nameDraft}
                    maxLength={160}
                    disabled={savingName}
                    onChange={(e) => setNameDraft(e.target.value)}
                  />
                  <button
                    className="btn btn-primary btn-sm"
                    type="submit"
                    data-busy={savingName}
                    disabled={
                      savingName
                      || !nameDraft.trim()
                      || nameDraft.trim() === community.name
                    }
                  >
                    Save
                  </button>
                </div>
              </form>
            </div>

            <div className="sec-title" style={{ marginTop: 26, marginBottom: 6 }}>
              Who can find and join
            </div>
            <p className="cm-hint" style={{ marginTop: 0 }}>
              Being listed and being joinable are separate — a community can be
              public to find and still invitation-only to get into.
            </p>

            {accessNotice && (
              <div className={accessNotice.tone === 'error' ? 'inline-error' : 'cm-role-ok'}>
                {accessNotice.text}
              </div>
            )}

            <div className="cm-choices">
              {ACCESS_MODES.map((option) => (
                <label
                  className={`cm-choice${
                    accessModeOf(community) === option.key ? ' on' : ''}`}
                  key={option.key}
                >
                  <input
                    type="radio"
                    name="access-mode"
                    value={option.key}
                    checked={accessModeOf(community) === option.key}
                    disabled={savingAccess}
                    onChange={() => handleAccessMode(option.key)}
                  />
                  <span>
                    <span className="t">{option.label}</span>
                    <span className="s">{option.hint}</span>
                  </span>
                </label>
              ))}
            </div>

            <div className="sec-title" style={{ marginTop: 26, marginBottom: 6 }}>
              Who can invite
            </div>
            <p className="cm-hint" style={{ marginTop: 0 }}>
              An invitation is an offer — the person you invite decides whether to
              accept it, and only then do they join.
            </p>

            {inviteNotice && (
              <div className={inviteNotice.tone === 'error' ? 'inline-error' : 'cm-role-ok'}>
                {inviteNotice.text}
              </div>
            )}

            <div className="cm-choices">
              {INVITE_POLICIES.map((option) => (
                <label
                  className={`cm-choice${
                    community.inviteMinRole === option.key ? ' on' : ''}`}
                  key={option.key}
                >
                  <input
                    type="radio"
                    name="invite-policy"
                    value={option.key}
                    checked={community.inviteMinRole === option.key}
                    disabled={savingInvite}
                    onChange={() => handleInvitePolicy(option.key)}
                  />
                  <span>
                    <span className="t">{option.label}</span>
                    <span className="s">{option.hint}</span>
                  </span>
                </label>
              ))}
            </div>

            <div className="sec-title" style={{ marginTop: 26, marginBottom: 6 }}>
              Who can post
            </div>
            <p className="cm-hint" style={{ marginTop: 0 }}>
              Reading, commenting and reacting are unaffected — this only controls
              who may start a post.
            </p>

            {policyNotice && (
              <div className={policyNotice.tone === 'error' ? 'inline-error' : 'cm-role-ok'}>
                {policyNotice.text}
              </div>
            )}

            <div className="cm-choices">
              {POST_POLICIES.map((option) => (
                <label
                  className={`cm-choice${
                    community.postMinRole === option.key ? ' on' : ''}`}
                  key={option.key}
                >
                  <input
                    type="radio"
                    name="post-policy"
                    value={option.key}
                    checked={community.postMinRole === option.key}
                    disabled={savingPolicy}
                    onChange={() => handlePostPolicy(option.key)}
                  />
                  <span>
                    <span className="t">{option.label}</span>
                    <span className="s">{option.hint}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {tab === 'Members' && (
          <>
            {roleNotice && (
              <div className={roleNotice.tone === 'error' ? 'inline-error' : 'cm-role-ok'}>
                {roleNotice.text}
              </div>
            )}

            {members.length === 0 ? (
              <p className="cm-hint">No members yet.</p>
            ) : (
              <div className="cm-members">
                {members.map((m) => {
                  // Same rule the server applies: you may only act on someone
                  // below your own rank, so the owner and your fellow admins
                  // render as a badge rather than a control.
                  const manageable = canManageMember(community.myRole, m.communityRole)
                  return (
                    <div className="cm-member" key={m.id}>
                      <Avatar initials={m.initials} color={m.color} size="sm" />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="t">{m.name}</div>
                        <div className="s">
                          {[m.role, m.company].filter(Boolean).join(' · ')}
                        </div>
                      </div>
                      {manageable ? (
                        <>
                          <select
                            className="cm-role"
                            value={m.communityRole}
                            disabled={roleBusyId === m.userId || removingId === m.userId}
                            aria-label={`Role for ${m.name}`}
                            onChange={(e) => handleRoleChange(m, e.target.value)}
                          >
                            {assignableRoles(community.myRole).map((r) => (
                              <option key={r.key} value={r.key}>{r.label}</option>
                            ))}
                          </select>
                          {confirmRemoveId === m.userId && (
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={() => setConfirmRemoveId(null)}
                              disabled={removingId === m.userId}
                            >
                              Cancel
                            </button>
                          )}
                          <button
                            className={`btn btn-sm ${
                              confirmRemoveId === m.userId ? 'btn-danger' : 'btn-ghost'}`}
                            onClick={() => handleRemoveMember(m)}
                            data-busy={removingId === m.userId}
                            disabled={removingId === m.userId}
                            title={`Remove ${m.name} from this community`}
                          >
                            {confirmRemoveId === m.userId ? 'Confirm' : 'Remove'}
                          </button>
                        </>
                      ) : (
                        <RoleBadge role={m.communityRole} />
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {canManageRoles(community.myRole) && (
              <p className="cm-hint cm-role-help">
                Moderators can delete posts and mute or remove members. Admins can
                also invite, ban, and manage channels and settings.
                {community.myRole === 'admin'
                  && ' Only the owner can appoint another admin.'}
                {' '}Removing someone ends their membership here only — their Deal
                Network account is untouched, and they can join again.
              </p>
            )}
          </>
        )}
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal}>Close</button>
      </ModalFoot>

      <GroupPhotoModal
        isOpen={showPhotoModal}
        onClose={() => setShowPhotoModal(false)}
        logoUrl={community?.logoUrl}
        initials={community?.initials}
        communityName={community?.name}
        bannerColor={community?.banner ? community.banner.replace('b', 'a') : 'a1'}
        onUploadPhoto={async (file) => {
          setSavingLogo(true)
          setLogoNotice(null)
          try {
            const media = await uploadMedia(file)
            const updated = await setCommunityLogo(activeSlug, media.path)
            setCommunity((c) => ({ ...c, logoUrl: updated.logoUrl }))
            setLogoNotice({ tone: 'ok', text: 'Picture updated.' })
            onChanged?.()
          } catch (err) {
            setLogoNotice({ tone: 'error', text: err.message })
          } finally {
            setSavingLogo(false)
          }
        }}
        onRemovePhoto={handleRemoveLogo}
        canEdit={canManageRoles(community?.myRole)}
        busy={savingLogo}
      />
    </Modal>
  )
}
