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

/** How it works — signing up to closing, in four steps. */
export const steps = [
  {
    n: 1,
    icon: 'profile',
    title: 'Create your profile',
    desc:
      'Sign in with Google or Apple, pick your role, and set the markets and asset classes you actually work in. Every field is public, members-only or private — your call.',
  },
  {
    n: 2,
    icon: 'communities',
    title: 'Join your communities',
    desc:
      'Communities are organised by location and asset class, so the people you meet are working the same streets and the same deal sizes as you.',
  },
  {
    n: 3,
    icon: 'mail',
    title: 'Run the deal in one place',
    desc:
      'Connect Gmail, move contacts into a pipeline, and share documents from a permissioned data room instead of a forwarded email chain.',
  },
  {
    n: 4,
    icon: 'bolt',
    title: 'Underwrite and decide',
    desc:
      'Drop the deal numbers into a template and get rate caps, sensitivity and a full model back — exported to Excel or PDF for the credit paper.',
  },
]

/** Why choose us — the six reasons that answer "why not a generic CRM?" */
export const whyUs = [
  {
    icon: 'stack',
    title: 'One platform, not six subscriptions',
    desc:
      'Forum, CRM, data room, analytics and underwriting behind one login — and one invoice at the end of the month.',
  },
  {
    icon: 'pin',
    title: 'Organised by market, not alphabetically',
    desc:
      'Communities, contacts, news and benchmarks are all filtered to the regions and asset classes you work in. Nothing else gets in.',
  },
  {
    icon: 'mail',
    title: 'Your inbox, already in the CRM',
    desc:
      'Connect Gmail once. Contacts and threads sync across on their own instead of being re-typed into a spreadsheet every Friday.',
  },
  {
    icon: 'lock',
    title: 'Your deal data stays yours',
    desc:
      'Field-by-field visibility, share links that expire, and AI that runs on your own key. We do not train anything on your deals.',
  },
  {
    icon: 'underwriting',
    title: 'Underwriting that is not a blank sheet',
    desc:
      'Templates by deal type, rate caps built in and sensitivity on tap — minutes rather than an afternoon of cell references.',
  },
  {
    icon: 'check',
    title: 'Early access pricing, locked in',
    desc:
      'Join in phase 1 and you keep the price you started on while the roadmap keeps shipping through phase 7.',
  },
]

/** Use cases — the jobs members actually open the platform to do. */
export const useCases = [
  {
    icon: 'investors',
    title: 'Raising equity for a scheme',
    desc:
      'Put the opportunity in front of investor groups in your market, control who sees which numbers, and keep every conversation on one pipeline.',
  },
  {
    icon: 'search',
    title: 'Sourcing off-market stock',
    desc:
      'Find the brokers, owners and sponsors working your asset class before the deal ever reaches a portal listing.',
  },
  {
    icon: 'dataroom',
    title: 'Running a live data room',
    desc:
      'One folder structure per deal, access provisioned party by party, and share links that expire when you say so — not when someone forwards them.',
  },
  {
    icon: 'bolt',
    title: 'Underwriting an acquisition',
    desc:
      'Templates, rate caps and sensitivity analysis in a single pass, exported straight to Excel or Word for the investment committee.',
  },
  {
    icon: 'plans',
    title: 'Placing debt',
    desc:
      'Get in front of lenders who actually write in your region and loan range, with the file ready to send rather than half-built.',
  },
  {
    icon: 'contacts',
    title: 'Keeping a team on one deal',
    desc:
      'Roles and permissions per member, so the pipeline is a single shared view instead of five private spreadsheets and a group chat.',
  },
]

/**
 * Who the platform is for. The five roles mirror `roleOptions` in
 * ./onboarding.js — the same list a new member picks from at sign-up.
 */
export const userTypes = [
  {
    icon: 'home',
    title: 'Developers & Sponsors',
    desc: 'You build or convert property and raise the capital for it.',
    points: ['Reach investor groups by market', 'A data room per scheme', 'Underwrite before you commit'],
  },
  {
    icon: 'investors',
    title: 'Investors & LPs',
    desc: 'You put capital into other people’s projects.',
    points: ['Deal flow filtered to your mandate', 'Sponsor profiles and track records', 'One record of what you were shown'],
  },
  {
    icon: 'contacts',
    title: 'Brokers & Agents',
    desc: 'You introduce buyers, sellers and tenants.',
    points: ['Buyers by market and asset class', 'Mandates and contacts in one CRM', 'Share particulars securely'],
  },
  {
    icon: 'plans',
    title: 'Lenders',
    desc: 'You provide construction or acquisition finance.',
    points: ['Requests that fit your box', 'Complete files, not fragments', 'Benchmark against market cap rates'],
  },
  {
    icon: 'profile',
    title: 'Service providers',
    desc: 'Architecture, legal, PM, valuation and similar.',
    points: ['Be found by people mid-deal', 'Publish coverage and credentials', 'Join the communities you serve'],
  },
]

/**
 * PLACEHOLDER COPY — illustrative quotes for the preview build, attributed to a
 * role rather than a person on purpose: no named individual has endorsed the
 * platform yet. Replace with real, attributed and signed-off testimonials
 * before this page goes live.
 */
export const testimonials = [
  {
    q: 'We were running one scheme across Gmail, a file-share, a spreadsheet and two group chats. Having the pipeline and the data room in the same place took about a week out of the raise.',
    who: 'Development director',
    org: 'Mixed-use sponsor',
    initials: 'DD',
    color: 'a1',
  },
  {
    q: 'The part that sold me was the filtering. I see the deals in my regions at my ticket size, and nothing else lands in front of me.',
    who: 'Investment manager',
    org: 'Private capital LP',
    initials: 'IM',
    color: 'a4',
  },
  {
    q: 'Expiring share links alone justify it. I know exactly who opened the file and I know the link is dead afterwards.',
    who: 'Head of acquisitions',
    org: 'Regional developer',
    initials: 'HA',
    color: 'a6',
  },
]

/** Trust and social proof — how member and deal information is handled. */
export const trust = [
  {
    icon: 'lock',
    title: 'Encrypted document storage',
    desc: 'Deal files sit in Cloudflare R2 with access provisioned per party, never behind an open public link.',
  },
  {
    icon: 'clock',
    title: 'Share links that expire',
    desc: 'External parties get token-based URLs that stop working on use, or on the deadline you set.',
  },
  {
    icon: 'profile',
    title: 'Field-by-field visibility',
    desc: 'Every profile field is public, members-only or private — set at sign-up and changeable any time.',
  },
  {
    icon: 'check',
    title: 'Sign in with Google or Apple',
    desc: 'OAuth only. There is no password for us to store, leak or lose on your behalf.',
  },
  {
    icon: 'bolt',
    title: 'Bring your own AI key',
    desc: 'Underwriting runs on your own OpenAI, Claude or Gemini account, and your deal data never trains our models.',
  },
  {
    icon: 'communities',
    title: 'Invitation and referral only',
    desc: 'Early access is closed by design. Members are people someone already in the network vouched for.',
  },
]

/** About us — who is building this and how. */
export const about = {
  title: 'Built by people who were running deals across six tools',
  body: [
    'Deal Network is being built for the people who actually put property deals together — developers, investors, brokers, lenders and the professionals around them. It started from a simple irritation: a single transaction spread across an inbox, a spreadsheet, a file-sharing account and three chat groups, with nobody sure which version was current.',
    'We are deliberately small, and deliberately public about the plan. The roadmap above is the real one — a working network first, then the CRM and the data room, then the analytics and AI layers on top. We would rather ship a phase that works than announce a feature that does not exist yet.',
    'Early access is invitation and referral only while we grow the first few hundred members, because a network of the right people beats a network of a lot of people.',
  ],
  points: [
    { n: 'Phase 1', l: 'Live now — profiles, communities, networking' },
    { n: '7 phases', l: 'Published roadmap, through to native apps' },
    { n: 'Invite only', l: 'How members join during early access' },
  ],
}

/** FAQs — the questions that come up before someone signs up. */
export const faqs = [
  {
    q: 'Who can join Deal Network?',
    a: 'Early access is invitation and referral only. It is built for property professionals — developers and sponsors, investors and LPs, brokers, lenders, and the service providers who work alongside them. You pick your role when you create your profile.',
  },
  {
    q: 'What does it cost?',
    a: 'Early access is free and does not need a card. Paid tiers add contacts, pipeline capacity, team seats and the later roadmap modules — the full comparison is on the pricing page, and you can change tier later.',
  },
  {
    q: 'Which parts are live today?',
    a: 'Phase 1 is live: profiles, communities, the networking hub and the public plans. The CRM, data room, analytics and AI underwriting arrive across phases 2 to 4 — open any phase card on this page for the full list of what is in it and where each item stands.',
  },
  {
    q: 'Is my deal information private?',
    a: 'You control your profile field by field: public, members-only or private. Documents in a data room are permissioned per party, shared through links that expire, and stored encrypted. Nothing about a deal is published unless you publish it.',
  },
  {
    q: 'Do you verify what other members post?',
    a: 'No. We do not verify, audit or endorse any information a member publishes about a property, a project or a deal. Treat the platform as an introduction, not as diligence — anything you rely on, you check yourself.',
  },
  {
    q: 'How does the Gmail connection work?',
    a: 'You authorise it once, and contacts and threads sync into your CRM instead of being re-entered by hand. It is optional, it is scoped to what the CRM needs, and you can disconnect it at any time from your profile.',
  },
  {
    q: 'Do I need my own AI account for underwriting?',
    a: 'Yes — AI underwriting is a Pro feature that runs on a key you provide, from OpenAI, Claude, Gemini or another provider. We supply the templates, formulas and outputs; the computation runs on your account, so your deal data stays under your control.',
  },
  {
    q: 'Can my whole team work in one place?',
    a: 'Yes. Roles and permissions per team member arrive with the CRM in phase 2, so a pipeline is one shared view with each person seeing what they should. The number of seats depends on your plan.',
  },
]

/**
 * The roadmap strip, on this page and on Pricing. Titles are the phase names in
 * ./phases.js so the two sections cannot drift apart; the descriptions are the
 * short form of the feature groups in that phase.
 */
export const roadmap = [
  { n: 1, title: 'Basic Platform', desc: 'Documentation pack, mock app, landing pages, legal documents, foundation.', now: true },
  { n: 2, title: 'CRM, Profiles and Networking', desc: 'Contacts, pipelines, profiles, communities, Stripe billing.' },
  { n: 3, title: 'Data Room and Basic Underwriting', desc: 'Permissioned data room, underwriting sandbox, deals, cap table.' },
  { n: 4, title: 'Advanced Underwriting and Analytics', desc: 'IRR and sensitivity, dashboards, exports, AI plugin.' },
  { n: 5, title: 'AI Agent and Regulatory / Cyber', desc: 'In-product AI agent, recommendations, spend caps, security review.' },
  { n: 6, title: 'Stabilisation, Native Planning, Interview, Team', desc: 'Defect burn-down, native rebuild, SOC 2 readiness, hiring.' },
  { n: 7, title: 'Native App and New Features', desc: 'iOS and Android release, custom dashboards and fields, governance.' },
]
