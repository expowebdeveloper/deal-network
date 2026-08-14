/**
 * Communities API calls plus the adapter between the API shape (snake_case)
 * and what the cards render.
 */

import { api } from './api'

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
    joined: c.joined,
    pending: c.pending,
    joinPolicy: c.join_policy,
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
    role: m.user?.role,
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

/** Posts belonging to one community — the modal's Discussion tab. */
export function listCommunityPosts(communityId, { limit = 10 } = {}) {
  return api.get(`/api/posts?community_id=${communityId}&limit=${limit}`)
}

export function createCommunityPost(communityId, body) {
  return api.post('/api/posts', { community_id: communityId, body })
}
