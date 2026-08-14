/** Feed, uploads and Home-rail API calls. */

import { api, API_URL, refreshSession, request, tokens } from './api'

/** Media URLs come back as /media/xyz.png — make them absolute for <img src>. */
export function mediaUrl(path) {
  if (!path) return ''
  return path.startsWith('http') ? path : `${API_URL}${path}`
}

export function toPost(p) {
  return {
    id: p.id,
    body: p.body,
    createdAt: p.created_at,
    visibility: p.visibility,
    author: {
      id: p.author.id,
      name: p.author.name,
      initials: p.author.initials,
      color: p.author.avatar_color,
      company: p.author.company,
      location: p.author.location,
    },
    community: p.community ? { id: p.community.id, name: p.community.name, slug: p.community.slug } : null,
    embed: p.embed_title ? { title: p.embed_title, detail: p.embed_detail } : null,
    attachments: (p.attachments || []).map((a) => ({
      id: a.id,
      kind: a.kind,
      url: mediaUrl(a.url),
      name: a.original_name,
      contentType: a.content_type,
      sizeBytes: a.size_bytes,
    })),
    likeCount: p.like_count,
    commentCount: p.comment_count,
    likedByMe: p.liked_by_me,
  }
}

export function listFeed({ limit = 20, offset = 0 } = {}) {
  return api.get(`/api/posts?limit=${limit}&offset=${offset}`).then((page) => ({
    ...page,
    items: page.items.map(toPost),
  }))
}

export function createPost(body) {
  return api.post('/api/posts', body).then(toPost)
}

export function toggleLike(postId) {
  return api.post(`/api/posts/${postId}/like`)
}

export function listComments(postId) {
  return api.get(`/api/posts/${postId}/comments`)
}

export function addComment(postId, body) {
  return api.post(`/api/posts/${postId}/comments`, { body })
}

export function deletePost(postId) {
  return api.delete(`/api/posts/${postId}`)
}

/**
 * Upload one file. Uses fetch directly rather than the JSON helper because the
 * body is multipart — the browser must set its own boundary header.
 */
export async function uploadMedia(file, _retried = false) {
  const form = new FormData()
  form.append('file', file)

  const response = await fetch(`${API_URL}/api/media`, {
    method: 'POST',
    headers: tokens.access ? { Authorization: `Bearer ${tokens.access}` } : {},
    body: form,
  })

  // Multipart cannot go through the JSON client, so replay the refresh here too —
  // otherwise an upload is the one call that fails when the token expires.
  if (response.status === 401 && !_retried) {
    const ok = await refreshSession()
    if (ok) return uploadMedia(file, true)
  }

  const text = await response.text()
  let payload = null
  try {
    payload = text ? JSON.parse(text) : null
  } catch {
    payload = text
  }

  if (!response.ok) {
    const detail =
      (payload && typeof payload === 'object' && payload.detail) ||
      (typeof payload === 'string' && payload) ||
      'Upload failed'
    throw new Error(Array.isArray(detail) ? detail.map((d) => d.msg).join(', ') : detail)
  }

  return {
    id: payload.id,
    kind: payload.kind,
    url: mediaUrl(payload.url),
    name: payload.original_name,
    contentType: payload.content_type,
    sizeBytes: payload.size_bytes,
  }
}

export function deleteMedia(id) {
  return request(`/api/media/${id}`, { method: 'DELETE' })
}

/* --- Home rails ---------------------------------------------------------- */

export function myStats() {
  return api.get('/api/me/stats')
}

export function suggestedCommunities(limit = 3) {
  return api.get(`/api/communities/suggested?limit=${limit}`)
}

export function suggestedMembers(limit = 2) {
  return api.get(`/api/members/suggested?limit=${limit}`)
}

/* --- Plans --------------------------------------------------------------- */

export function listPlans() {
  return api.get('/api/plans')
}

/** The same price list, for visitors who have not signed in yet. */
export function fetchPlanCatalogue() {
  return api.get('/api/plans/catalogue', { auth: false })
}

export function selectPlan(plan) {
  return api.post('/api/plans/select', { plan })
}

export function currentSelection() {
  return api.get('/api/plans/selection')
}

/** What my plan unlocks: modules, feature ticks, contact limit and usage. */
export function fetchEntitlements() {
  return api.get('/api/plans/entitlements')
}

/** "2h", "5d" — the compact stamp the feed uses. */
export function timeAgo(iso) {
  const seconds = Math.max(1, (Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d`
  return `${Math.floor(seconds / 604800)}w`
}

export function fileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
