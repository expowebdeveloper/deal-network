/** Contacts: the API calls and the shape the table and board render. */

import { api, ApiError } from './api'

/* --- Calls ---------------------------------------------------------------- */

export function listContacts({ q = '', stage = '', limit = 100 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (q) params.set('q', q)
  if (stage) params.set('stage', stage)
  return api.get(`/api/contacts?${params}`)
}

/** The five board columns. 403s for a plan without the pipeline tick. */
export function fetchPipeline() {
  return api.get('/api/contacts/pipeline')
}

export function createContact(body) {
  return api.post('/api/contacts', body)
}

/** One call per card move. */
export function moveContact(id, stage) {
  return api.put(`/api/contacts/${id}/stage`, { stage })
}

export function deleteContact(id) {
  return api.delete(`/api/contacts/${id}`)
}

/* --- Reading errors the API is specific about ----------------------------- */

/** True when a call was refused because the plan does not carry the feature. */
export function isUpgradeRequired(error) {
  return error instanceof ApiError && error.status === 403
    && error.body?.detail === 'upgrade_required'
}

/** True when the free tier's contact ceiling was hit. */
export function isContactLimitReached(error) {
  return error instanceof ApiError && error.status === 403
    && error.body?.detail === 'contact_limit_reached'
}

/* --- Display -------------------------------------------------------------- */

/** "Yesterday", "4 days ago", "3 weeks ago" — the wording the table uses. */
export function touchLabel(iso) {
  if (!iso) return '—'
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  const weeks = Math.floor(days / 7)
  if (weeks < 5) return weeks === 1 ? '1 week ago' : `${weeks} weeks ago`
  const months = Math.floor(days / 30)
  return months === 1 ? '1 month ago' : `${months} months ago`
}

/**
 * The API's snake_case row, as the screen wants it. `stage` needs no mapping:
 * the backend's ContactStage values are the column labels.
 */
export function toContact(row) {
  return {
    id: row.id,
    name: row.name,
    company: row.company || 'No company',
    role: row.role || '—',
    market: row.market || '—',
    short: row.market_short || row.market || '—',
    stage: row.stage,
    source: row.source || 'Added by you',
    touch: touchLabel(row.last_touch_at || row.created_at),
    initials: row.initials,
    color: row.avatar_color,
    email: row.email,
    phone: row.phone,
  }
}
