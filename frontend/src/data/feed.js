/** Home feed posts. `body` is split into paragraphs of plain text + <strong> runs. */
export const posts = [
  {
    id: 'p1',
    author: { name: 'Priya Nair', initials: 'PN', color: 'a3' },
    sub: [
      { text: 'Nair Estates · Bangalore · posted in ' },
      { text: 'Bangalore Developers', bold: true },
      { text: ' · 2h' },
    ],
    tag: { variant: 'shared', label: 'Community post' },
    body: [
      { text: 'Approvals came through this week on our ' },
      { text: '120-unit build in Whitefield', strong: true },
      {
        text:
          '. Two years from land acquisition to sanction, which is faster than the last one. ' +
          'Happy to compare notes with anyone navigating BBMP timelines right now — the pre-submission checklist made most of the difference.',
      },
    ],
    likes: 34,
    comments: 12,
  },
  {
    id: 'p2',
    author: { name: 'Sarah Whitfield', initials: 'SW', color: 'a2' },
    sub: [
      { text: 'Whitfield Capital · New York · posted in ' },
      { text: 'New York Multifamily', bold: true },
      { text: ' · 5h' },
    ],
    tag: { variant: 'shared', label: 'Community post' },
    body: [
      {
        text:
          'Genuine question for the operators here — are you seeing cap rates settle in the outer boroughs, ' +
          'or is the spread still all over the place? Everything I’ve underwritten this quarter has come back 40–60bps apart on comparable assets.',
      },
    ],
    likes: 58,
    comments: 27,
  },
  {
    id: 'p3',
    author: { name: 'Michael Trent', initials: 'MT', color: 'a6' },
    sub: [{ text: 'Coastal Ridge Partners · New York · 1d' }],
    body: [
      {
        text:
          'Wrapped construction on the Bay Street conversion. 64 units, mixed-use ground floor. ' +
          'Full write-up going out to the investor group this week.',
      },
    ],
    embed: {
      title: 'Bay Street Conversion — completion note',
      detail: '64 residential units · 8,400 sq ft retail · Staten Island, NY',
      tags: [
        { variant: 'public', label: 'Public summary' },
        { variant: 'private', label: 'Financials private' },
      ],
    },
    likes: 91,
    comments: 19,
  },
]

export const networkStats = [
  { l: 'Connections', v: '128' },
  { l: 'Communities', v: '4' },
  { l: 'Profile views · 30d', v: '342' },
]

export const communitiesToJoin = [
  { initials: 'MU', color: 'a4', title: 'Mixed-Use Developers', sub: '431 members' },
  { initials: 'MH', color: 'a5', title: 'Medical & Healthcare Property', sub: '265 members' },
  { initials: 'NY', color: 'a2', title: 'New York Multifamily', sub: '1,204 members' },
]

export const peopleYouMayKnow = [
  {
    initials: 'DO', color: 'a2',
    title: 'Daniel Ortiz', sub: 'Cascade Equity · Bay Area',
    person: { name: 'Daniel Ortiz', company: 'Cascade Equity', location: 'Bay Area, US', role: 'Investor', color: 'a2', initials: 'DO' },
  },
  {
    initials: 'AR', color: 'a5',
    title: 'Anita Rao', sub: 'Southbridge Credit · Bangalore',
    person: { name: 'Anita Rao', company: 'Southbridge Credit', location: 'Bangalore, IN', role: 'Lender', color: 'a5', initials: 'AR' },
  },
]
