import { useCallback, useEffect, useRef, useState } from 'react'
import Avatar from '../ui/Avatar'
import { Loading, ErrorState } from '../ui/States'
import { CloseIcon, CheckIcon, CameraIcon, SettingsIcon, PhotoIcon } from '../icons/Icons'
import { ACCEPT, uploadMedia } from '../../lib/feed'
import { useApp } from '../../context/AppContext'
import GroupPhotoModal from './GroupPhotoModal'
import {
  getCommunity, memberLabel,
  assignableRoles, canManageMember, canManageRoles, changeMemberRole,
  roleErrorMessage, roleLabel,
  POST_POLICIES, setPostPolicy,
  ACCESS_MODES, INVITE_POLICIES, accessModeOf, communityErrorMessage,
  isDraft, publishCommunity, setAccessMode, setInvitePolicy,
  renameCommunity, setCommunityLogo, removeMember, listCommunityMembers,
  listJoinRequests, approveJoinRequest, declineJoinRequest,
} from '../../lib/communities'

const ROLE_TAG = { owner: 'gold', admin: 'internal', moderator: 'shared' }

/** The access mode as a single word, for the chip in the header. */
function accessLabel(community) {
  return ACCESS_MODES.find((m) => m.key === accessModeOf(community))?.chip || 'Public'
}

export default function CommunitySettingsDrawer({ slug, onChanged }) {
  const { closeModal } = useApp()
  const [activeSlug, setActiveSlug] = useState(slug)
  useEffect(() => { setActiveSlug(slug) }, [slug])

  const [community, setCommunity] = useState(null)
  const [members, setMembers] = useState([])
  const [requests, setRequests] = useState([])
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  // Identity state
  const [nameDraft, setNameDraft] = useState('')
  const [savingName, setSavingName] = useState(false)
  const [nameNotice, setNameNotice] = useState(null)
  const [savingLogo, setSavingLogo] = useState(false)
  const [logoNotice, setLogoNotice] = useState(null)
  const [showPhotoModal, setShowPhotoModal] = useState(false)
  const logoInput = useRef(null)

  // Policy states
  const [savingAccess, setSavingAccess] = useState(false)
  const [accessNotice, setAccessNotice] = useState(null)
  const [savingInvite, setSavingInvite] = useState(false)
  const [inviteNotice, setInviteNotice] = useState(null)
  const [savingPolicy, setSavingPolicy] = useState(false)
  const [policyNotice, setPolicyNotice] = useState(null)

  // Publishing state
  const [publishing, setPublishing] = useState(false)
  const [publishError, setPublishError] = useState(null)

  // Member management state
  const [roleBusyId, setRoleBusyId] = useState(null)
  const [roleNotice, setRoleNotice] = useState(null)
  const [removingId, setRemovingId] = useState(null)
  const [confirmRemoveId, setConfirmRemoveId] = useState(null)

  // Join request state
  const [requestBusyId, setRequestBusyId] = useState(null)

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      const detail = await getCommunity(activeSlug)
      setCommunity(detail)
      setNameDraft(detail.name)
      setStatus('ready')

      listCommunityMembers(activeSlug)
        .then((m) => setMembers(m.items))
        .catch(() => setMembers([]))

      if (canManageRoles(detail.myRole)) {
        listJoinRequests(activeSlug)
          .then((reqs) => setRequests(Array.isArray(reqs) ? reqs : []))
          .catch(() => setRequests([]))
      }
    } catch (err) {
      setError(err)
      setStatus('error')
    }
  }, [activeSlug])

  useEffect(() => { load() }, [load])

  async function handleRename(e) {
    e.preventDefault()
    const next = nameDraft.trim()
    if (!next || next === community.name) return
    setSavingName(true)
    setNameNotice(null)
    try {
      const updated = await renameCommunity(activeSlug, next)
      setActiveSlug(updated.slug)
      setCommunity((c) => ({
        ...c, name: updated.name, slug: updated.slug, initials: updated.initials,
      }))
      setNameDraft(updated.name)
      setNameNotice({ tone: 'ok', text: 'Saved community name.' })
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

  async function handleLogo(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
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
  }

  async function handleRemoveLogo() {
    setSavingLogo(true)
    setLogoNotice(null)
    try {
      const updated = await setCommunityLogo(activeSlug, null)
      setCommunity((c) => ({ ...c, logoUrl: updated.logoUrl }))
      setLogoNotice({ tone: 'ok', text: 'Removed picture.' })
      onChanged?.()
    } catch (err) {
      setLogoNotice({ tone: 'error', text: err.message })
    } finally {
      setSavingLogo(false)
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
      setAccessNotice({
        tone: 'error',
        text: communityErrorMessage(err, 'Could not change access mode.'),
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
        text: communityErrorMessage(err, 'Could not change invite policy.'),
      })
    } finally {
      setSavingInvite(false)
    }
  }

  async function handlePostPolicy(next) {
    if (next === community.postMinRole) return
    setSavingPolicy(true)
    setPolicyNotice(null)
    try {
      const updated = await setPostPolicy(activeSlug, next)
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
      setPublishError(communityErrorMessage(err, 'Could not publish community.'))
    } finally {
      setPublishing(false)
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
      setRoleNotice({ tone: 'error', text: roleErrorMessage(err, nextRole) })
    } finally {
      setRoleBusyId(null)
    }
  }

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
        text: communityErrorMessage(err, 'Could not remove member.'),
      })
    } finally {
      setRemovingId(null)
      setConfirmRemoveId(null)
    }
  }

  async function handleApproveRequest(req) {
    const userId = req.user?.id || req.userId
    setRequestBusyId(userId)
    setRoleNotice(null)
    try {
      await approveJoinRequest(activeSlug, userId)
      setRequests((rows) => rows.filter((r) => (r.user?.id || r.userId) !== userId))
      setCommunity((c) => ({
        ...c, memberCount: (c.memberCount || 0) + 1,
      }))
      setRoleNotice({ tone: 'ok', text: `Approved ${req.user?.name || 'user'}'s request.` })
      listCommunityMembers(activeSlug).then((m) => setMembers(m.items)).catch(() => {})
      onChanged?.()
    } catch (err) {
      setRoleNotice({
        tone: 'error',
        text: communityErrorMessage(err, 'Could not approve request.'),
      })
    } finally {
      setRequestBusyId(null)
    }
  }

  async function handleDeclineRequest(req) {
    const userId = req.user?.id || req.userId
    setRequestBusyId(userId)
    setRoleNotice(null)
    try {
      await declineJoinRequest(activeSlug, userId)
      setRequests((rows) => rows.filter((r) => (r.user?.id || r.userId) !== userId))
      setRoleNotice({ tone: 'ok', text: `Declined ${req.user?.name || 'user'}'s request.` })
      onChanged?.()
    } catch (err) {
      setRoleNotice({
        tone: 'error',
        text: communityErrorMessage(err, 'Could not decline request.'),
      })
    } finally {
      setRequestBusyId(null)
    }
  }

  // Editing the picture is an admin capability — the same one the lightbox
  // checks before it offers Change and Remove.
  const canEditPhoto = canManageRoles(community?.myRole)

  // Whether the name field holds something worth saving. Trimmed on both sides,
  // so trailing whitespace alone is not a change.
  const nameDirty = Boolean(
    community && nameDraft.trim() && nameDraft.trim() !== community.name,
  )

  return (
    <div className="drawer-backdrop" onClick={closeModal}>
      <aside className="side-drawer" onClick={(e) => e.stopPropagation()}>
        {/* The header carries two things at once: what this panel is, and which
            community it is acting on. Keeping the name out of the title line —
            in an identity row of its own — means the title stays the same
            size and weight whether the community is called "Miami" or
            "Greater Miami Industrial Developers Network". */}
        <header className="drawer-head">
          <div className="drawer-head-bar">
            <div className="drawer-head-titles">
              <span className="drawer-eyebrow">
                <SettingsIcon />
                Manage community
              </span>
              <h2>Community Settings</h2>
            </div>
            <button className="drawer-close-btn" onClick={closeModal} aria-label="Close settings">
              <CloseIcon />
            </button>
          </div>

          {community && (
            <div className="drawer-head-identity">
              <Avatar
                initials={community.initials}
                color={community.banner.replace('b', 'a')}
                size="sm"
                src={community.logoUrl}
                alt=""
              />
              <div className="drawer-head-meta">
                <span className="drawer-head-name" title={community.name}>
                  {community.name}
                </span>
                <span className="drawer-head-sub">
                  {memberLabel(community.memberCount)}
                </span>
              </div>
              <span className={`drawer-state-chip${isDraft(community) ? ' draft' : ''}`}>
                {isDraft(community) ? 'Draft' : accessLabel(community)}
              </span>
            </div>
          )}
        </header>

        <div className="drawer-body">
          {status === 'loading' && <Loading label="Loading settings…" />}
          {status === 'error' && <ErrorState error={error} onRetry={load} />}

          {status === 'ready' && community && (
            <div className="drawer-content-stack">
              {/* Draft notification card */}
              {isDraft(community) && (
                <div className="cm-draft">
                  <div>
                    <span className="t">This community is a draft</span>
                    <span className="s">
                      Publish it to make it discoverable to other members.
                    </span>
                  </div>
                  {canManageRoles(community.myRole) && (
                    <button
                      className="btn btn-primary btn-sm"
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

              {/* Section 1: Identity */}
              <section className="drawer-section">
                <div className="drawer-section-head">
                  <h3>Identity &amp; branding</h3>
                  <p>The picture and name people see everywhere this community appears.</p>
                </div>

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

                {/* The photo, WhatsApp's way round: the picture itself is the
                    viewer — tapping it opens the full-size lightbox — and the
                    camera badge is the editor. Two targets, each doing one
                    obvious thing, instead of a row of buttons under the avatar
                    where "View photo", "Change" and "Remove" all looked alike.
                    Removing lives inside the lightbox, next to the photo it
                    removes. */}
                <div className="cm-photo-block">
                  <div className="cm-photo">
                    <button
                      type="button"
                      className="wa-avatar-wrap"
                      onClick={() => setShowPhotoModal(true)}
                      aria-label={
                        community.logoUrl
                          ? `View the ${community.name} photo`
                          : `${community.name} has no photo yet`
                      }
                    >
                      <Avatar
                        initials={community.initials}
                        color={community.banner.replace('b', 'a')}
                        size="lg"
                        src={community.logoUrl}
                        alt=""
                      />
                      <span className="wa-avatar-overlay" aria-hidden="true">
                        <PhotoIcon />
                        <span className="wa-avatar-overlay-text">View photo</span>
                      </span>
                    </button>

                    {canEditPhoto && (
                      <button
                        type="button"
                        className="wa-photo-fab"
                        onClick={() => logoInput.current?.click()}
                        data-busy={savingLogo}
                        disabled={savingLogo}
                        aria-label={
                          community.logoUrl ? 'Change community photo' : 'Add a community photo'
                        }
                        title={community.logoUrl ? 'Change photo' : 'Add photo'}
                      >
                        <CameraIcon />
                      </button>
                    )}

                    <input
                      ref={logoInput}
                      type="file"
                      accept={ACCEPT.image}
                      className="hidden"
                      onChange={handleLogo}
                    />
                  </div>

                  <p className="cm-photo-hint">
                    {savingLogo
                      ? 'Uploading…'
                      : canEditPhoto
                        ? 'Tap the photo to view it, or the camera to change it.'
                        : 'Tap the photo to view it.'}
                  </p>
                </div>

                <form className="cm-name-field" onSubmit={handleRename}>
                  <label htmlFor="drawer-community-name">Community name</label>
                  <div className="cm-name-row">
                    <input
                      id="drawer-community-name"
                      className="input"
                      value={nameDraft}
                      maxLength={160}
                      disabled={savingName}
                      placeholder="What is this community called?"
                      onChange={(e) => setNameDraft(e.target.value)}
                    />
                    {/* Only present once the name has actually been changed.
                        A permanently-visible Save that is disabled nine times
                        out of ten is furniture: it takes space in the row,
                        invites a click that does nothing, and says nothing
                        about whether there is anything to save. Its appearing
                        *is* the "you have unsaved changes" signal.

                        It stays through the save itself — `community.name` only
                        catches up once the request succeeds — so the busy state
                        has somewhere to show, and it leaves on its own when the
                        two match again. */}
                    {nameDirty && (
                      <button
                        className="btn btn-primary btn-sm cm-name-save"
                        type="submit"
                        data-busy={savingName}
                        disabled={savingName}
                      >
                        Save
                      </button>
                    )}
                  </div>
                  {/* The name is the one control here that does not save on
                      change, so it is the one that has to say so. */}
                  <span className="cm-field-note">
                    Renaming also updates the community&rsquo;s link.
                  </span>
                </form>
              </section>

              {/* Section 2: Who can find and join */}
              <section className="drawer-section">
                <div className="drawer-section-head">
                  <h3>Who can find and join</h3>
                  <p>Who can see this community, and what happens when they ask to join.</p>
                </div>

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
                        name="drawer-access-mode"
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
              </section>

              {/* Section 3: Who can invite */}
              <section className="drawer-section">
                <div className="drawer-section-head">
                  <h3>Who can invite</h3>
                  <p>The lowest role allowed to bring someone new in.</p>
                </div>

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
                        name="drawer-invite-policy"
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
              </section>

              {/* Section 4: Who can post */}
              <section className="drawer-section">
                <div className="drawer-section-head">
                  <h3>Who can post</h3>
                  <p>The lowest role allowed to start a post here.</p>
                </div>

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
                        name="drawer-post-policy"
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
              </section>

              {/* Section 5: Members & Roles */}
              <section className="drawer-section">
                <div className="drawer-section-head">
                  <h3>Members and roles</h3>
                  <p>Change what someone can do here, or remove them.</p>
                </div>

                {roleNotice && (
                  <div className={roleNotice.tone === 'error' ? 'inline-error' : 'cm-role-ok'}>
                    {roleNotice.text}
                  </div>
                )}

                {requests.length > 0 && (
                  <div className="cm-join-requests">
                    <div className="cm-join-requests-head">
                      <h4>Pending Join Requests ({requests.length})</h4>
                      <span className="cm-join-requests-flag">Action required</span>
                    </div>
                    <div className="cm-members">
                      {requests.map((r) => {
                        const targetUser = r.user || {}
                        const uid = targetUser.id || r.userId
                        return (
                          <div className="cm-member" key={r.id || uid}>
                            <Avatar initials={targetUser.initials || 'U'} color={targetUser.avatar_color || 'a1'} size="sm" />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div className="t">{targetUser.name || 'Member Candidate'}</div>
                              <div className="s">{targetUser.email}</div>
                            </div>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button
                                className="btn btn-primary btn-sm"
                                onClick={() => handleApproveRequest(r)}
                                disabled={requestBusyId === uid}
                              >
                                Approve
                              </button>
                              <button
                                className="btn btn-ghost btn-sm"
                                onClick={() => handleDeclineRequest(r)}
                                disabled={requestBusyId === uid}
                              >
                                Decline
                              </button>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {members.length === 0 ? (
                  <p className="cm-hint">No members found.</p>
                ) : (
                  <div className="cm-members">
                    {members.map((m) => {
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
                                title={`Remove ${m.name}`}
                              >
                                {confirmRemoveId === m.userId ? 'Confirm' : 'Remove'}
                              </button>
                            </>
                          ) : (
                            <span className="drawer-role-tag">{roleLabel(m.communityRole)}</span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </section>
            </div>
          )}
        </div>

        {/* Everything in this panel except the name saves the moment it is
            changed, so "Done" closes rather than commits. Saying so is what
            stops it reading like a form someone could lose work in. */}
        <footer className="drawer-foot">
          <span className="drawer-foot-note">Changes save as you make them</span>
          <button className="btn btn-primary" onClick={closeModal}>
            <CheckIcon />
            Done
          </button>
        </footer>
      </aside>

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
    </div>
  )
}
