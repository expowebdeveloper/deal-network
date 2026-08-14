/** Adapters between the API's user shape and what the components render. */

import { api, request } from './api'

/* --- Terms ---------------------------------------------------------------- */

/** The text in force and whether you have agreed to it. Open to anyone. */
export function fetchTerms() {
  return request('/api/terms')
}

/** Agree to the version you were shown. Both required boxes must be true. */
export function acceptTerms({ version, marketingOptIn = false }) {
  return api.post('/api/terms/accept', {
    version,
    accept_terms: true,
    accept_unverified: true,
    marketing_opt_in: marketingOptIn,
  })
}

/* --- Profile -------------------------------------------------------------- */

/** Edit profile. Only the keys you send are changed; blank clears a field. */
export function updateMe(changes) {
  return api.patch('/api/me', changes)
}

/** Connections and communities, which the profile row above cannot know. */
export function fetchMyStats() {
  return api.get('/api/me/stats')
}

/** What you tell investors you are looking for. */
export function fetchMandate() {
  return api.get('/api/me/mandate')
}

export function updateMandate(changes) {
  return api.put('/api/me/mandate', changes)
}

/** The public / members / private choice for each profile field. */
export function fetchVisibility() {
  return api.get('/api/me/visibility')
}

export function setVisibility(fieldKey, level) {
  return api.put('/api/me/visibility', { field_key: fieldKey, level })
}

/* --- Profile setup -------------------------------------------------------- */

/** The steps, the options each one offers, and anything already answered. */
export function fetchOnboarding() {
  return api.get('/api/onboarding')
}

/** Step 1 — what describes you best. */
export function chooseRole(role) {
  return api.post('/api/onboarding/role', { role })
}

/** Step 2 — company details. Finishing this is what ends setup. */
export function completeProfileSetup(details) {
  return api.post('/api/onboarding/profile', details)
}

/** 'Vikram Sethi' -> 'VS'. Mirrors the backend's derive_initials. */
export function initialsFor(name = '', email = '') {
  const parts = name.replace(/-/g, ' ').split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return email.slice(0, 2).toUpperCase()
}

/**
 * The API returns snake_case with nullable profile fields (a brand-new OAuth
 * account has only an email and a name). This fills the gaps the UI assumes.
 *
 * `stats` is the counts row: connections and communities are counted by
 * GET /api/me/stats, so pass that in — without it those two read zero.
 */
export function toDisplayUser(user, stats = null) {
  if (!user) return null
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    initials: user.initials || initialsFor(user.name, user.email),
    color: user.avatar_color || 'a1',
    company: user.company || 'No company yet',
    title: user.title || user.role || 'Member',
    location: user.location || 'Location not set',
    focus: user.focus || 'Add your asset classes',
    stats: [
      { n: String(stats?.connections ?? 0), l: 'Connections' },
      { n: String(stats?.communities ?? 0), l: 'Communities' },
      { n: String(user.completed_projects ?? 0), l: 'Completed projects' },
      { n: String(user.profile_views ?? 0), l: 'Profile views' },
    ],
  }
}

/**
 * The line under each field-visibility row.
 *
 * Two of the eight are not stored anywhere — they describe a rule rather than a
 * value — so they read as the rule. The rest come from the live profile, which
 * is what makes editing show up here.
 */
export function describeField(id, user, mandate) {
  switch (id) {
    case 'company':
      return user?.company || 'Not set'
    case 'markets':
      return mandate?.markets || user?.location || 'Not set'
    case 'completed':
      return `${user?.completed_projects ?? 0} projects · ${user?.units_delivered ?? 0} units delivered`
    case 'raise':
      return mandate?.typical_raise || 'Not set'
    case 'active':
      return `${user?.active_projects ?? 0} active sites`
    case 'contact':
      return user?.email || 'Not set'
    case 'lenders':
    case 'investors':
      return 'Never shown to other members'
    default:
      return 'Not set'
  }
}
