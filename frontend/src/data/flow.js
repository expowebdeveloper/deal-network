/**
 * The "How it connects" map.
 *
 * `action` is a descriptor the FlowView turns into a click handler:
 *   { modal: 'landing', props }  — open a modal
 *   { nav: '/profile' }          — close the overlay and navigate
 *   { signOut: true }            — back to the sign-in screen
 * A node with no action and `locked: true` is a not-yet-built step.
 *
 * `tags` are keys into the legend below.
 */
export const legend = [
  { key: 'pub', variant: 'public', label: 'Public', note: 'anyone can see' },
  { key: 'shd', variant: 'shared', label: 'Members', note: 'signed-in members' },
  { key: 'priv', variant: 'private', label: 'Private', note: 'only the owner' },
  { key: 'int', variant: 'internal', label: 'Internal', note: 'operational records' },
]

export const TAGS = {
  pub: { variant: 'public', label: 'Public' },
  shd: { variant: 'shared', label: 'Members' },
  priv: { variant: 'private', label: 'Private' },
  int: { variant: 'internal', label: 'Internal' },
  soon: { variant: 'soon', label: 'SOON' },
}

// The modal loads the community from the API, so it only needs the slug.
const SAMPLE_COMMUNITY_SLUG = 'bangalore-developers'


export const bands = [
  {
    label: 'Arriving',
    nodes: [
      { title: 'Referral or ad', desc: 'Someone hears about the network', action: { modal: 'landing' } },
      { title: 'Landing page', desc: 'What they see before an account', action: { modal: 'landing' } },
      { title: 'Sign in', desc: 'Google or Apple — nothing else to remember', action: { signOut: true }, cls: 'entry' },
      { title: 'Terms & consent', desc: 'Storage, retention, and what we do not verify', tags: ['int'], action: { modal: 'terms' } },
    ],
  },
  {
    label: 'Setting up',
    nodes: [
      { title: 'Role', desc: 'Developer, investor, broker, lender or service provider', tags: ['pub'], action: { modal: 'role' } },
      { title: 'Profile setup', desc: 'Company, market, asset classes', tags: ['pub', 'shd'], action: { modal: 'wizard' } },
      { title: 'Profile', desc: 'Field-by-field visibility control', tags: ['pub', 'shd', 'priv'], action: { nav: '/profile' } },
    ],
  },
  {
    label: 'Finding people',
    nodes: [
      { title: 'Home', desc: 'Activity from your communities and connections', action: { nav: '/' } },
      { title: 'Communities', desc: 'By market and by asset class', tags: ['shd'], action: { nav: '/communities' } },
      { title: 'Join or create', desc: 'Open, request-to-join, or invite only', tags: ['shd'], action: { nav: '/communities' } },
      { title: 'Posts & channels', desc: 'Discussion inside each community', tags: ['shd'], action: { modal: 'community', props: { slug: SAMPLE_COMMUNITY_SLUG } } },
    ],
  },
  {
    label: 'Building relationships',
    nodes: [
      { title: 'Members', desc: 'Search across every market', tags: ['pub'], action: { nav: '/members' } },
      { title: 'Connect', desc: 'Works across markets — no regional wall', tags: ['shd'], action: { nav: '/members' } },
      { title: 'Investors', desc: 'Who follows you, who asked for an introduction', tags: ['shd', 'priv'], action: { nav: '/investors' } },
      { title: 'Contacts', desc: 'Your own pipeline — never shared', tags: ['priv', 'int'], action: { nav: '/contacts' } },
    ],
  },
  {
    label: 'Paying',
    nodes: [
      { title: 'Plans', desc: 'Early access now, then $25 or $100', action: { nav: '/plans' } },
      { title: 'Checkout', desc: 'Card stored, not charged until launch', tags: ['int'], action: { modal: 'checkout', props: { plan: 'Member', price: '25' } } },
      { title: 'Subscription live', desc: 'Seats and limits apply from here', tags: ['int'], action: { nav: '/plans' } },
    ],
  },
  {
    label: 'Next to build',
    nodes: [
      { title: 'Data Room', desc: 'Upload, controlled access, expiring links', tags: ['priv', 'soon'], locked: true },
      { title: 'Underwriting', desc: 'Templates in, model out', tags: ['priv', 'soon'], locked: true },
      { title: 'Analytics', desc: 'Market benchmarks from pooled activity', tags: ['pub', 'shd', 'int', 'soon'], locked: true },
      { title: 'Assistant', desc: 'Answers questions about your own data', tags: ['priv', 'soon'], locked: true },
    ],
  },
]
