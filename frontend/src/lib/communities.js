/**
 * Communities API calls plus the adapter between the API shape (snake_case)
 * and what the cards render.
 */

import { api } from './api'
import { mediaUrl } from './feed'

/** "1 member" / "342 members" */
export function memberLabel(count) {
  return `${(count ?? 0).toLocaleString()} ${count === 1 ? 'member' : 'members'}`
}

/** API community -> the shape the cards and modal expect. */
export function toCommunity(c) {
  return {
    id: c.id,
    slug: c.slug,
    name: c.name,
    kind: c.kind,
    location: c.location,
    desc: c.description || '',
    banner: c.banner,
    initials: c.initials,
    // Absolute, for <img src>. Null means the community has no picture and the
    // initials bubble stands in.
    logoUrl: c.logo_url ? mediaUrl(c.logo_url) : null,
    joined: c.joined,
    pending: c.pending,
    // The caller's role in *this* community, not their profession.
    myRole: c.my_role || null,
    joinPolicy: c.join_policy,
    // 'Public' | 'Members' | 'Private'. Paired with joinPolicy it gives the
    // access modes below — see ACCESS_MODES.
    visibility: c.visibility || 'Public',
    // 'draft' until it is published, then 'active'. A draft is visible only to
    // the people building it.
    status: c.status || 'active',
    publishedAt: c.published_at || null,
    // Lowest role allowed to post; 'member' means everyone.
    postMinRole: c.post_min_role || 'member',
    // Lowest role allowed to invite; 'admin' is the default.
    inviteMinRole: c.invite_min_role || 'admin',
    count: (c.member_count ?? 0).toLocaleString(),
    memberCount: c.member_count ?? 0,
    faces: (c.faces || []).map((f) => ({
      initials: f.initials,
      color: f.avatar_color,
      name: f.name,
    })),
    channels: c.channels || [],
  }
}

export function toMember(m) {
  return {
    id: m.id,
    userId: m.user?.id,
    name: m.user?.name,
    initials: m.user?.initials,
    color: m.user?.avatar_color,
    company: m.user?.company,
    // `role` is the member's profession (developer, investor, broker…).
    // `communityRole` is their standing *inside* this community. Two different
    // things that the API happens to spell the same way at different levels.
    role: m.user?.role,
    communityRole: m.role || 'member',
    isAdmin: m.is_admin,
    status: m.status,
  }
}

/** filter is one of: all | region | industry | joined */
export function listCommunities({ filter = 'all', q = '', limit = 48 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (filter === 'region' || filter === 'industry') params.set('kind', filter)
  if (filter === 'joined') params.set('joined', 'true')
  if (q.trim()) params.set('q', q.trim())

  return api.get(`/api/communities?${params}`).then((page) => ({
    ...page,
    items: page.items.map(toCommunity),
  }))
}

export function getCommunity(slug) {
  return api.get(`/api/communities/${slug}`).then(toCommunity)
}

export function createCommunity(body) {
  return api.post('/api/communities', body).then(toCommunity)
}

export function updateCommunity(slug, body) {
  return api.patch(`/api/communities/${slug}`, body).then(toCommunity)
}

export function deleteCommunity(slug) {
  return api.delete(`/api/communities/${slug}`)
}

export function joinCommunity(slug) {
  return api.post(`/api/communities/${slug}/join`).then((r) => ({
    status: r.status,
    community: toCommunity(r.community),
  }))
}

export function leaveCommunity(slug) {
  return api.delete(`/api/communities/${slug}/leave`)
}

export function listCommunityMembers(slug, { limit = 24 } = {}) {
  return api.get(`/api/communities/${slug}/members?limit=${limit}`).then((page) => ({
    ...page,
    items: page.items.map(toMember),
  }))
}

export function listJoinRequests(slug) {
  return api.get(`/api/communities/${slug}/requests`).then((rows) => rows.map(toMember))
}

export function approveRequest(slug, userId) {
  return api.post(`/api/communities/${slug}/requests/${userId}/approve`)
}

export function declineRequest(slug, userId) {
  return api.post(`/api/communities/${slug}/requests/${userId}/decline`)
}

export const approveJoinRequest = approveRequest
export const declineJoinRequest = declineRequest

import { toPost } from './feed'

/** Posts belonging to one community — the modal's Discussion tab. */
export function listCommunityPosts(communityId, { limit = 10 } = {}) {
  return api.get(`/api/posts?community_id=${communityId}&limit=${limit}`).then((page) => ({
    ...page,
    items: page.items.map(toPost),
  }))
}

export function createCommunityPost(communityId, body, attachmentIds = []) {
  return api.post('/api/posts', {
    community_id: communityId,
    body,
    attachment_ids: attachmentIds,
  })
}

/* --- Community roles ------------------------------------------------------ */

/**
 * The five roles, weakest first. `rank` mirrors ROLE_RANK in the backend's
 * models/base.py — the UI must not offer a change the server is going to
 * refuse, so the same ordering has to exist on both sides.
 */
export const COMMUNITY_ROLES = [
  {
    key: 'viewer', label: 'Viewer', rank: 0,
    hint: 'Read and download only — cannot post, comment or react.',
  },
  {
    key: 'member', label: 'Member', rank: 1,
    hint: 'Post, comment, react and take part.',
  },
  {
    key: 'moderator', label: 'Moderator', rank: 2,
    hint: 'Also delete posts, and mute or remove members.',
  },
  {
    key: 'admin', label: 'Admin', rank: 3,
    hint: 'Also invite and ban members, and manage channels and settings.',
  },
  {
    key: 'owner', label: 'Owner', rank: 4,
    hint: 'Full control, including ownership transfer.',
  },
]

const BY_KEY = Object.fromEntries(COMMUNITY_ROLES.map((r) => [r.key, r]))

export function roleLabel(key) {
  return BY_KEY[key]?.label || 'Member'
}

function rankOf(key) {
  return BY_KEY[key]?.rank ?? 0
}

/** Owners and admins hold MANAGE_ROLES; moderators and members do not. */
export function canManageRoles(myRole) {
  return myRole === 'owner' || myRole === 'admin'
}

/**
 * Whether `myRole` may act on a member currently holding `targetRole`.
 *
 * Strictly-greater, matching `outranks()` on the server: equal ranks do not
 * outrank each other, so an admin cannot touch another admin and nobody can
 * touch the owner.
 */
export function canManageMember(myRole, targetRole) {
  return canManageRoles(myRole) && rankOf(myRole) > rankOf(targetRole)
}

/**
 * The roles `myRole` is allowed to grant.
 *
 * Owner is deliberately absent: assigning it transfers the community and demotes
 * the person doing it, which is not something a dropdown should do without its
 * own confirmed flow. Moderator is always present even when the plan does not
 * include one — the refusal, and the upgrade it names, comes from the server.
 */
export function assignableRoles(myRole) {
  if (!canManageRoles(myRole)) return []
  return COMMUNITY_ROLES.filter((r) => r.key !== 'owner' && rankOf(myRole) > r.rank)
}

/* --- Who may post --------------------------------------------------------- */

/**
 * The three settings the owner picks between, weakest gate first. These are
 * roles, not a separate policy vocabulary — `post_min_role` is compared through
 * the same rank ladder as everything else, so "Admins only" simply means the
 * lowest rank that clears the gate is admin.
 */
export const POST_POLICIES = [
  { key: 'member', label: 'Everyone', hint: 'Any member can post.' },
  {
    key: 'moderator', label: 'Moderators and admins',
    hint: 'Ordinary members can read and comment, but not start a post.',
  },
  { key: 'admin', label: 'Admins only', hint: 'The community reads as an announcement feed.' },
]

/** Whether the signed-in member clears this community's posting gate. */
export function canPostIn(community) {
  if (!community?.joined) return false
  return rankOf(community.myRole) >= rankOf(community.postMinRole || 'member')
}

/**
 * Why they cannot post, or '' when they can.
 *
 * Worded identically to POST_REFUSAL in the backend's community_permissions.py,
 * so the sentence does not change depending on whether it was the UI or the API
 * that turned them away.
 */
export function postRefusalMessage(community) {
  const min = community?.postMinRole || 'member'
  if (community?.myRole === 'viewer') return 'Viewers cannot post in this community.'
  if (min === 'owner') return 'Only the owner can post in this community.'
  if (min === 'admin') return 'Only admins can post in this community.'
  if (min === 'moderator') return 'Only moderators and admins can post in this community.'
  return ''
}

/** Change who may post. Owner and admins only, enforced server-side. */
export function setPostPolicy(slug, role) {
  return updateCommunity(slug, { post_min_role: role })
}

/* --- Draft and publish ---------------------------------------------------- */

/** A community that has been created but never published. */
export function isDraft(community) {
  return community?.status === 'draft'
}

/**
 * Take a draft live.
 *
 * Until this is called the community is visible only to the people building it:
 * it does not appear in anyone else's browse list, cannot be read, joined or
 * invited into. Publishing is one-way — taking a live community down again is
 * archiving, which is a different thing.
 */
export function publishCommunity(slug) {
  return api.post(`/api/communities/${slug}/publish`).then(toCommunity)
}

/* --- Who can find and join ------------------------------------------------ */

/**
 * The four ways a community can be reached.
 *
 * `visibility` and `join_policy` are two independent columns on the server, but
 * only some pairings are meaningful and a member should not have to reason
 * about the product of two enums. These are the combinations, named for what
 * they do rather than for the fields behind them.
 *
 * Private is paired with invite deliberately: a community nobody can find, with
 * a join button nobody can reach, would be a setting with no effect.
 */
// `label` is the sentence on the radio card; `chip` is the same state in one
// or two words, for the badge in the settings header where a full label would
// wrap. They must not drift apart — the chip is a shorthand for the label, not
// a different fact.
export const ACCESS_MODES = [
  {
    key: 'open',
    label: 'Public',
    chip: 'Public',
    hint: 'Anyone can find it and join straight away.',
    visibility: 'Public',
    joinPolicy: 'open',
  },
  {
    key: 'request',
    label: 'Public, approval to join',
    chip: 'Approval',
    hint: 'Anyone can find it and ask; an admin approves each request.',
    visibility: 'Public',
    joinPolicy: 'request',
  },
  {
    key: 'invite',
    label: 'Public, invitation to join',
    chip: 'Invite only',
    hint: 'Listed for everyone, but only people who are invited can join.',
    visibility: 'Public',
    joinPolicy: 'invite',
  },
  {
    key: 'private',
    label: 'Private',
    chip: 'Private',
    hint: 'Hidden from everyone. Only people you invite can find it or join.',
    visibility: 'Private',
    joinPolicy: 'invite',
  },
]

/** Which mode a community is currently in. Falls back to the closest match. */
export function accessModeOf(community) {
  const visibility = community?.visibility || 'Public'
  const policy = community?.joinPolicy || 'open'
  const exact = ACCESS_MODES.find(
    (m) => m.visibility === visibility && m.joinPolicy === policy,
  )
  if (exact) return exact.key
  // Anything not public is private as far as this control is concerned; the
  // member-only visibility has no mode of its own here.
  return visibility === 'Public' ? 'open' : 'private'
}

/** Apply one of ACCESS_MODES. Both fields move together, in one PATCH. */
export function setAccessMode(slug, key) {
  const mode = ACCESS_MODES.find((m) => m.key === key)
  if (!mode) return Promise.reject(new Error('Unknown access mode'))
  return updateCommunity(slug, {
    visibility: mode.visibility,
    join_policy: mode.joinPolicy,
  })
}

/* --- Who can invite ------------------------------------------------------- */

/**
 * The lowest role allowed to send an invitation, weakest gate last — the same
 * shape as POST_POLICIES, and read through the same rank ladder.
 *
 * `viewer` is deliberately not offered: a viewer is read-only, and the server
 * rejects it as a floor because it would gate nothing.
 */
export const INVITE_POLICIES = [
  {
    key: 'admin', label: 'Admins only',
    hint: 'Only the owner and admins can invite someone in.',
  },
  {
    key: 'moderator', label: 'Moderators and admins',
    hint: 'Moderators can also bring people in.',
  },
  {
    key: 'member', label: 'Any member',
    hint: 'Anyone already in the community can invite someone new.',
  },
]

/** Change who may invite. Owner and admins only, enforced server-side. */
export function setInvitePolicy(slug, role) {
  return updateCommunity(slug, { invite_min_role: role })
}

/* --- Identity: name and picture ------------------------------------------ */

/**
 * Rename a community.
 *
 * The server regenerates the slug and the initials from the new name, so the
 * reply carries a *different* slug to the one that was sent. Callers holding a
 * slug — the modal does — have to adopt the one that comes back or their next
 * request 404s.
 */
export function renameCommunity(slug, name) {
  return updateCommunity(slug, { name })
}

/**
 * Set the community's picture.
 *
 * Takes the server-relative path from `uploadMedia`, not its display URL: the
 * value is stored on the row and has to resolve from any host. Pass null to
 * clear it and fall back to the initials.
 */
export function setCommunityLogo(slug, path) {
  return updateCommunity(slug, { logo_url: path })
}

/* --- Removing a member ---------------------------------------------------- */

/**
 * Remove someone from the community.
 *
 * The membership ends and they may rejoin — this is not a ban, which is a
 * separate action that also blocks coming back. Their Deal Network account is
 * untouched either way.
 *
 * Only on /api/v1: the pre-v1 surface never had a remove endpoint, and
 * `changeMemberRole` already reaches across for the same reason.
 */
export function removeMember(communityRef, userId) {
  return api.post(`/api/v1/communities/${communityRef}/members/${userId}/remove`)
}

/** PATCH the member's role. Accepts a slug or an id — the API resolves both. */
export function changeMemberRole(communityRef, userId, role) {
  return api
    .patch(`/api/v1/communities/${communityRef}/members/${userId}/role`, { role })
    .then(toMember)
}

/* --- Reading refusals the API is specific about --------------------------- */

/**
 * The plan-related codes POST /api/communities answers with, as sentences.
 *
 * The API returns short stable codes so clients can branch on them; showing one
 * to a member raw ("community_limit_reached") is not an error message. The
 * upgrade the server named travels in `X-Required-Plan`, so the wording can say
 * which plan actually lifts the limit rather than guessing.
 */
//: Display names, matching PLAN_NAMES in the backend's services/billing.py.
//: The keys stay the enum codes the API speaks.
const PLAN_NAMES = {
  early_access: 'Freemium', member: 'Silver', professional: 'Gold',
}

export function communityErrorMessage(error, fallback = 'Could not create the community.') {
  const detail = error?.body?.detail
  // /api/v1 answers with the structured shape instead of a bare detail string.
  const structured = error?.body?.error
  const upgrade = error?.headers?.get?.('x-required-plan')
    || structured?.details?.upgrade_plan
  const plan = PLAN_NAMES[upgrade] || 'a paid plan'

  if (detail === 'community_limit_reached'
      || structured?.code === 'COMMUNITY_LIMIT_REACHED') {
    const limit = error?.headers?.get?.('x-community-limit')
      || structured?.details?.limit
    if (limit === '0' || limit === 0) {
      return `Creating communities is not included in Freemium. `
        + `Upgrade to ${plan} to start one.`
    }
    return limit === '1' || limit === 1
      ? `Silver includes one community. Upgrade to ${plan} to create more.`
      : `You have reached your plan's limit of ${limit} communities. `
        + `Upgrade to ${plan} to create more.`
  }
  if (detail === 'upgrade_required' || structured?.code === 'ENTITLEMENT_REQUIRED') {
    return `That option is not included in your plan. Upgrade to ${plan} to use it.`
  }
  if (structured?.message) return structured.message
  if (typeof detail === 'string' && !detail.includes('_')) return detail
  return error?.message || fallback
}

/**
 * Why a role change was refused, as a sentence.
 *
 * The moderator ceiling is an entitlement, so Early access ($0) answers
 * ENTITLEMENT_REQUIRED with `limit: 0` the first time anyone is promoted, and a
 * paid plan answers the same way once its allowance is used up. Both name the
 * cheapest plan that would lift the ceiling in `upgrade_plan`, so the wording
 * can point somewhere specific instead of saying "upgrade" and stopping.
 */
export function roleErrorMessage(error, role) {
  const structured = error?.body?.error
  const details = structured?.details || {}

  if (structured?.code === 'ENTITLEMENT_REQUIRED') {
    const upgrade = PLAN_NAMES[details.upgrade_plan] || 'a paid plan'
    const current = PLAN_NAMES[details.current_plan]
    const noun = role === 'moderator' ? 'Moderators' : 'That role'

    if (details.limit === 0) {
      return current
        ? `${noun} are not included in ${current}. Upgrade to ${upgrade} to appoint one.`
        : `${noun} are not included in your plan. Upgrade to ${upgrade} to appoint one.`
    }
    return `This community already has its limit of ${details.limit} `
      + `${details.limit === 1 ? 'moderator' : 'moderators'}. `
      + `Upgrade to ${upgrade} to appoint more.`
  }

  // Rank refusals already read as sentences — the server wrote them for a person.
  if (structured?.code === 'ROLE_CHANGE_NOT_ALLOWED') return structured.message

  return communityErrorMessage(error, 'Could not change that member\u2019s role.')
}
