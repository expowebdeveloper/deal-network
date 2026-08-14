export const roleOptions = [
  { title: 'Developer / Sponsor', desc: 'I build or convert property and raise capital for it' },
  { title: 'Investor / LP', desc: 'I put capital into other people’s projects' },
  { title: 'Broker / Agent', desc: 'I introduce buyers, sellers and tenants' },
  { title: 'Lender', desc: 'I provide construction or acquisition finance' },
  { title: 'Service provider', desc: 'Architecture, legal, PM, valuation and similar' },
]

export const termsChecks = [
  { id: 'terms', text: ['I accept the ', { b: 'Terms of Use' }, ' and ', { b: 'Privacy Policy' }, ', including the data storage and retention terms above.'] },
  { id: 'unverified', text: ['I understand information published by other members is ', { b: 'not verified' }, ' by this platform.'] },
  { id: 'updates', text: ['Send me occasional product updates. ', { muted: 'Optional.' }], optional: true },
]

export const termsCopy = [
  { h: 'What we store.', p: 'Your profile, company details, community activity, contacts and anything you upload are stored on our servers.' },
  { h: 'How long we keep it.', p: 'Information you add is retained for as long as your account exists, and for a defined period after you close it. It is not deleted automatically.' },
  { h: 'What we do not do.', p: 'We do not verify, audit or endorse any information a member publishes about a property, a project or a deal. Anything you rely on, you check yourself.' },
  { h: 'Who can see your information.', p: 'You control this field by field from your profile. Some operational staff can access stored data to run and support the service.' },
]

export const landingColumns = [
  { t: 'Find your market', d: 'Communities organised by city and by asset class.' },
  { t: 'Control what shows', d: 'Field-by-field: public, members only, or private.' },
  { t: 'Keep your relationships', d: 'Contacts and a pipeline that stay yours.' },
]

export const assetClassChips = [
  { label: 'Residential', on: true },
  { label: 'Mixed-use', on: true },
  { label: 'Medical' },
  { label: 'Industrial' },
  { label: 'Retail' },
  { label: 'Hospitality' },
]
