// The member list itself comes from GET /api/members — see Members.jsx. What is
// left here is the role filter, which is UI configuration rather than data: the
// keys are the MemberRole values the API filters on, and the labels are what the
// chips read.
export const memberFilters = [
  { key: 'all', label: 'All' },
  { key: 'Developer', label: 'Developers' },
  { key: 'Investor', label: 'Investors' },
  { key: 'Broker', label: 'Brokers' },
  { key: 'Lender', label: 'Lenders' },
]
