export const VISIBILITY_OPTIONS = ['Public', 'Members', 'Private']

/**
 * The field-visibility rows on the profile screen.
 *
 * `id` matches the backend's field keys (see services/users.py VISIBILITY_LABELS)
 * — the levels are stored per field via PUT /api/me/visibility. The value shown
 * under each label comes from the live profile; see describeField in lib/user.js.
 */
export const visibilityFields = [
  { id: 'company', k: 'Company name' },
  { id: 'markets', k: 'Markets' },
  { id: 'completed', k: 'Completed projects' },
  { id: 'raise', k: 'Typical raise size' },
  { id: 'active', k: 'Current projects in progress' },
  { id: 'contact', k: 'Email and phone' },
  { id: 'lenders', k: 'Lenders and loan terms' },
  { id: 'investors', k: 'Investor names' },
]
