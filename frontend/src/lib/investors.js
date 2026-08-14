/** The investor-facing side: overview tiles, introductions and follows. */

import { api } from './api'
import { timeAgo } from './feed'

/** The member directory, for picking who to ask about. */
export function listMembers({ q = '', limit = 50 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (q) params.set('q', q)
  return api.get(`/api/members?${params}`)
}

export function fetchOverview() {
  return api.get('/api/investors/overview')
}

/** `direction` is 'incoming' (asked of you) or 'outgoing' (you asked). */
export function listIntroductions(direction = 'incoming') {
  return api.get(`/api/investors/introductions?direction=${direction}`)
}

/** Ask to be introduced. Member and up — see require_feature. */
export function requestIntroduction({ toUserId, viaCommunityId = null, message = null }) {
  return api.post('/api/investors/introductions', {
    to_user_id: toUserId,
    via_community_id: viaCommunityId,
    message,
  })
}

/** Accepting also drops the requester into your contacts as a new lead. */
export function respondToIntroduction(id, accept) {
  return api.post(`/api/investors/introductions/${id}/respond`, { accept })
}

export function followMember(id) {
  return api.post(`/api/investors/follow/${id}`)
}

export function unfollowMember(id) {
  return api.delete(`/api/investors/follow/${id}`)
}

/** The tiles across the top, in the order the screen shows them. */
export function toTiles(overview) {
  if (!overview) return []
  return [
    { n: String(overview.investors_following), l: 'Investors following you' },
    {
      n: String(overview.introduction_requests),
      l: 'Introduction requests',
      d: overview.awaiting_reply ? `${overview.awaiting_reply} awaiting reply` : null,
    },
    { n: String(overview.profile_views), l: 'Profile views · 30d' },
    { n: String(overview.shared_communities), l: 'Shared communities' },
  ]
}

const STATUS_TAG = {
  pending: { variant: 'gold', label: 'Pending' },
  accepted: { variant: 'public', label: 'Connected' },
  declined: { variant: 'private', label: 'Declined' },
}

/**
 * One row of the introductions list. `direction` decides whose name to show:
 * an incoming request is about who asked, an outgoing one about who you asked.
 */
export function toIntroduction(row, direction = 'incoming') {
  const person = direction === 'incoming' ? row.from_user : row.to_user
  const via = row.via_community ? `via ${row.via_community.name}` : null
  const what = direction === 'incoming'
    ? (row.status === 'pending' ? 'asked to be introduced' : `introduction ${row.status}`)
    : (row.status === 'pending' ? 'you asked for an introduction' : `introduction ${row.status}`)

  return {
    id: row.id,
    status: row.status,
    personId: person.id,
    initials: person.initials,
    color: person.avatar_color,
    title: [person.name, person.company].filter(Boolean).join(' · '),
    sub: [person.location, via, what, timeAgo(row.created_at)].filter(Boolean).join(' · '),
    message: row.message,
    tag: STATUS_TAG[row.status] ?? STATUS_TAG.pending,
  }
}
