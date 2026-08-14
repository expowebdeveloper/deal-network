/**
 * Content for the public landing page (../components/landing/Landing.jsx).
 *
 * `icon` names a component in components/icons/Icons.jsx — the mapping lives in
 * the Landing component so this file stays plain data.
 */

export const heroStats = [
  { n: '3,770', l: 'Members' },
  { n: '8', l: 'Communities' },
  { n: '12', l: 'Markets' },
]

export const benefits = [
  { icon: 'clock', n: 'Save 10+ hrs', l: 'back every week' },
  { icon: 'bolt', n: '5 minutes', l: 'to a full underwrite' },
  { icon: 'mail', n: '1 inbox', l: 'Gmail synced, not re-typed' },
  { icon: 'stack', n: '1 platform', l: 'instead of six' },
]

/** The modules, each opening a detail modal. */
export const modules = [
  {
    id: 'forum',
    avatar: 'a1',
    phase: 'Phase 1',
    icon: 'forum',
    title: 'Online Forum & Networking Hub',
    blurb:
      'A members-only forum and directory to find developers, investors, brokers and lenders in your market.',
    detail: {
      summary:
        'The starting point of the network: profiles, communities and contacts built for property people, organised by the regions and asset classes they actually work in.',
      bullets: [
        'Investor and developer/professional profiles',
        'Industry and location-based communities',
        'Posts, discussions and direct networking',
        'Community admin and community profile pages',
        'Group and community management tools',
      ],
      status: 'Available from Phase 1 · expands in Phase 2',
    },
  },
  {
    id: 'news',
    avatar: 'a2',
    phase: 'Phase 2',
    icon: 'news',
    title: 'Niche News & Market Analysis',
    blurb:
      'Curated market intel and niche news feeds, so you stay ahead of your market without hunting across ten sites.',
    detail: {
      summary:
        'A feed of the market and location-specific news that actually affects your deals, alongside aggregated stats pulled from real activity on the network.',
      bullets: [
        'Location and asset-class specific news feed',
        'Aggregated market statistics and cap rates',
        'Benchmark view against comparable markets',
        'Clear separation of public vs. private data sources',
      ],
      status: 'Ships in Phase 2, deepens with Analytics in Phase 4',
    },
  },
  {
    id: 'crm',
    avatar: 'a3',
    phase: 'Phase 2',
    icon: 'mail',
    title: 'CRM & Deal Pipeline — connect your Gmail',
    blurb:
      'Manage contacts, deals and pipelines in one place. Connect your inbox once and stop re-entering the same information.',
    detail: {
      summary:
        'A CRM built around real-estate deal flow, not generic sales. Connect Gmail so contacts and threads sync automatically instead of living in two places.',
      bullets: [
        'Gmail connect & sync — no manual re-entry',
        'Deal pipelines with custom stages',
        'Roles and permissions per team member',
        'Pricing plans and payment gateway built in',
        'Full contact and relationship history',
      ],
      status: 'Core of Phase 2',
    },
  },
  {
    id: 'dataroom',
    avatar: 'a4',
    phase: 'Phase 2–3',
    icon: 'dataroom',
    title: 'Integrated Data & Deal Room',
    blurb:
      'Secure, permissioned document storage for every deal — Excel, PPT, PDFs and property files, all in one folder structure.',
    detail: {
      summary:
        'One place to store and share everything about a deal, with access control down to the individual file and link.',
      bullets: [
        'Upload Excel, PPT, PDFs and property/deal documents',
        'Folder structure (library) per deal or sponsor',
        'Access provisioning for external parties, with signup/password',
        'Token-based share URLs that expire after use',
        'Cloudflare R2-backed secure cloud storage',
      ],
      status: 'Rolls out across Phase 2 and Phase 3',
    },
  },
  {
    id: 'lp',
    avatar: 'a5',
    phase: 'Phase 2',
    icon: 'communities',
    title: 'Smarter LP & Capital Sourcing',
    blurb:
      'Reach the right LPs and capital partners faster with investor groups built around your markets and asset classes.',
    detail: {
      summary:
        'Capital sourcing shouldn’t be a cold-email spreadsheet. Investor groups and profiles make it easier to find and be found by the right counterparties.',
      bullets: [
        'Investor groups organised by region and asset class',
        'Investor and external-viewer profiles',
        'Controlled visibility for external investors/viewers',
        'Pricing tiers that scale reach as you grow',
      ],
      status: 'Ships in Phase 2',
    },
  },
  {
    id: 'analytics',
    avatar: 'a6',
    phase: 'Phase 3–4',
    icon: 'analytics',
    title: 'Analytics',
    blurb:
      'Turn raw deal data into dashboards — benchmarks, reports and exports, without opening a blank spreadsheet.',
    detail: {
      summary:
        'Everything collected in the data room and underwriting sandbox becomes a smart analytics layer: stored, aggregated and presented back to you.',
      bullets: [
        'Analytics dashboard with benchmark views',
        'Area, range and market aggregates',
        'Sensitivity analysis and underwriting insights/flags',
        'Reports and exports as PDF or Excel',
        'Data classification: public, private and internal',
      ],
      status: 'Foundations in Phase 3, full build-out in Phase 4',
    },
  },
  {
    id: 'ai',
    avatar: 'a7',
    phase: 'Phase 4',
    pro: true,
    icon: 'bolt',
    title: 'AI Underwriting in as little as 5 minutes',
    blurb:
      'Drop in the deal information and get a full underwriting model back — rate caps, sensitivity and outputs, in minutes.',
    detail: {
      summary:
        'Predefined underwriting templates plus your own AI key. The platform supplies the model and formulas; the computation runs on the AI account you connect, so your deal data stays yours.',
      bullets: [
        'Predefined underwriting templates by deal type',
        'Rate cap calculations built in',
        'Excel and Word based outputs',
        'Sensitivity analysis and underwriting insights',
        'Bring your own AI — OpenAI, Claude, Gemini or others',
      ],
      status: 'Sandbox in Phase 3, full AI layer in Phase 4–5 · Pro feature',
    },
  },
]

export const roadmap = [
  { n: 1, title: 'Basic Platform', desc: 'PRD, mock app, Google login, legal terms, 2 landing pages.', now: true },
  { n: 2, title: 'CRM & Networking', desc: 'CRM, pipelines, roles, pricing tiers, Stripe, communities.' },
  { n: 3, title: 'Data Room & Underwriting', desc: 'Data room, maps, cap rate, acquisition analytics.' },
  { n: 4, title: 'Analytics + AI Plugin', desc: 'Analytics layer and AI plugin for financial modeling.' },
  { n: 5, title: 'AI Agent of Platform', desc: 'Regulatory and cyber review, platform-wide AI agent.' },
  { n: 6, title: 'Stabilisation', desc: 'Native app planning, new product interviews, team scale-up.' },
  { n: 7, title: 'Native App', desc: 'Native app PRD and new features.' },
]
