/** Content for the presenter drawer. Internal notes — not member-facing. */

export const openDecisions = [
  {
    q: 'Can a member in one market connect into another?',
    prop: ['Built as ', { b: 'yes, unrestricted' }, '. A builder in Mohali can send a request to New York exactly like a local one.'],
    risk: 'If it should be walled by market, the member directory, search and suggestions all change shape.',
  },
  {
    q: 'Who is allowed to create a community?',
    prop: ['Built as ', { b: 'paid members only' }, ', with three join settings: open, request-to-join, invite-only.'],
    risk: 'If anyone can create one, expect duplicate and abandoned communities early. If only staff can, growth slows.',
  },
  {
    q: 'Is the network free, or paid from day one?',
    prop: ['Built as ', { b: 'free early access now' }, ', with $25 and $100 switching on once the first few hundred members are in.'],
    risk: 'This was said both ways on the call. It changes the whole signup funnel, so it needs settling before build.',
  },
  {
    q: 'What exactly belongs in the investor area?',
    prop: ['Built as ', { b: 'followers, introduction requests, stated mandate and visibility' }, '. No live deal listings yet.'],
    risk: 'Listings and documents are the next thing being built — if they belong here instead, the layout changes.',
  },
  {
    q: 'Does paying gate the network, or only the tools?',
    prop: ['Built so ', { b: 'the network stays reachable' }, ' and the paid tiers unlock contacts, pipeline and community creation.'],
    risk: 'Gating the network itself would suppress the member growth the pricing depends on.',
  },
]

export const changedRows = [
  { item: '$25 fee', was: 'Charged at signup', now: 'Pricing starts later, at 100–300 members' },
  { item: 'Tiers', was: '25 / 99 / 249 / 600', now: 'Two tiers: 25 and 100' },
  { item: 'Free tier', was: 'Free forever for investors', now: '“No free tier” — then “maybe networking stays free”' },
  { item: 'Sign in', was: 'Google', now: ['Google ', { b: 'and Apple' }] },
  { item: 'Deal map', was: 'Shared deal map', now: ['Private deal map + shared deal ', { i: 'analytics' }, ' map'] },
  { item: 'Data classes', was: '3 levels', now: [{ b: '4' }, ' — adds records kept for our own reporting'] },
  { item: 'AI reading user data', was: 'Platform analyses uploads', now: 'Rejected. We supply the template and formulas; their AI runs it' },
]

export const referenceShots = [
  { nm: 'HiveBright', ph: 'Onboarding and member profiles' },
  { nm: 'GoHighLevel', ph: 'Communities, contacts and pipeline' },
  { nm: 'DocSend', ph: 'Controlled document access — for the next build' },
]

export const standingNote = '“Open to adjusting based on SaaS feedback.”'
