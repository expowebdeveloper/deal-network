/** kind: 'region' (a market) or 'industry' (an asset class). */
export const communities = [
  {
    id: 'bangalore-developers',
    name: 'Bangalore Developers',
    kind: 'region',
    location: 'Bangalore, IN',
    count: '342',
    banner: 'b1',
    initials: 'BD',
    joined: true,
    desc: 'Residential and mixed-use developers operating across Bangalore and the wider Karnataka corridor.',
    faces: [
      { initials: 'PN', color: 'a3' },
      { initials: 'AR', color: 'a5' },
      { initials: 'KV', color: 'a6' },
    ],
  },
  {
    id: 'new-york-multifamily',
    name: 'New York Multifamily',
    kind: 'region',
    location: 'New York, US',
    count: '1,204',
    banner: 'b2',
    initials: 'NY',
    joined: true,
    desc: 'Sponsors, brokers and LPs active in the five boroughs and the tri-state multifamily market.',
    faces: [
      { initials: 'SW', color: 'a2' },
      { initials: 'MT', color: 'a6' },
      { initials: 'JF', color: 'a4' },
    ],
  },
  {
    id: 'mohali-tricity-builders',
    name: 'Mohali & Tricity Builders',
    kind: 'region',
    location: 'Mohali, IN',
    count: '187',
    banner: 'b6',
    initials: 'MT',
    joined: true,
    desc: 'Builders and land aggregators across Mohali, Chandigarh and Panchkula.',
    faces: [
      { initials: 'VS', color: 'a1' },
      { initials: 'HS', color: 'a3' },
    ],
  },
  {
    id: 'apartment-operators',
    name: 'Apartment Operators',
    kind: 'industry',
    location: 'Global',
    count: '890',
    banner: 'b4',
    initials: 'AO',
    joined: true,
    desc: 'Anyone building, owning or operating multifamily and serviced apartment stock.',
    faces: [
      { initials: 'SW', color: 'a2' },
      { initials: 'VS', color: 'a1' },
      { initials: 'DK', color: 'a5' },
    ],
  },
  {
    id: 'medical-healthcare-property',
    name: 'Medical & Healthcare Property',
    kind: 'industry',
    location: 'Global',
    count: '265',
    banner: 'b5',
    initials: 'MH',
    joined: false,
    desc: 'Hospitals, clinics, diagnostic centres and senior living — development and acquisition.',
    faces: [
      { initials: 'RM', color: 'a4' },
      { initials: 'TC', color: 'a3' },
    ],
  },
  {
    id: 'mixed-use-developers',
    name: 'Mixed-Use Developers',
    kind: 'industry',
    location: 'Global',
    count: '431',
    banner: 'b3',
    initials: 'MU',
    joined: false,
    desc: 'Ground-floor retail over residential, live-work schemes and podium developments.',
    faces: [
      { initials: 'MT', color: 'a6' },
      { initials: 'LB', color: 'a2' },
    ],
  },
  {
    id: 'valley-developers',
    name: 'Valley Developers',
    kind: 'industry',
    location: 'Bay Area, US',
    count: '156',
    banner: 'b1',
    initials: 'VD',
    joined: false,
    desc: 'Tech-corridor development — campus, R&D and workforce housing around the Bay Area.',
    faces: [
      { initials: 'DO', color: 'a2' },
      { initials: 'EN', color: 'a4' },
    ],
  },
  {
    id: 'industrial-warehousing',
    name: 'Industrial & Warehousing',
    kind: 'industry',
    location: 'Global',
    count: '298',
    banner: 'b6',
    initials: 'IW',
    joined: false,
    desc: 'Logistics parks, cold storage and last-mile distribution assets.',
    faces: [
      { initials: 'AR', color: 'a5' },
      { initials: 'PG', color: 'a6' },
    ],
  },
]

export const communityFilters = [
  { key: 'all', label: 'All', group: 'Type' },
  { key: 'region', label: 'By market', group: 'Type' },
  { key: 'industry', label: 'By asset class', group: 'Type' },
  { key: 'joined', label: 'Joined', group: 'Membership' },
]

/** Discussion shown inside the community modal. */
export const communityThread = [
  {
    author: { name: 'Priya Nair', initials: 'PN', color: 'a3' },
    sub: 'Nair Estates · 2h',
    body: 'Approvals came through on the 120-unit build this week. Happy to compare notes on timelines.',
  },
  {
    author: { name: 'Anita Rao', initials: 'AR', color: 'a5' },
    sub: 'Southbridge Credit · 1d',
    body: 'Construction finance rates have moved again. Posting a short summary in the finance channel.',
  },
]

export const communityChannels = ['# general', '# approvals', '# finance', '# introductions']

export const communityFaces = [
  { initials: 'PN', color: 'a3' },
  { initials: 'AR', color: 'a5' },
  { initials: 'KV', color: 'a6' },
  { initials: 'VS', color: 'a1' },
]
