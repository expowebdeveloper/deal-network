/**
 * The build plan, phase by phase — the content behind the phase cards on the
 * landing page (components/landing/Landing.jsx) and the detail dialog they open
 * (components/modals/PhaseModal.jsx).
 *
 * Every code, label, status and note below is transcribed verbatim from
 * card.txt in the repository root, which is the extract of the feature
 * checklist. `icon`, `avatar` and `blurb` are the only presentational
 * additions; icons are named as in components/landing/moduleIcons.js.
 *
 * To change what a phase contains, change card.txt and re-transcribe — the two
 * are meant to say the same thing.
 */

export const phases = [
  {
    n: 1,
    name: 'Basic Platform',
    icon: 'stack',
    avatar: 'a1',
    blurb:
      'The planning pack, the mock app, the landing pages, the legal documents, the first advertising and the platform foundation — everything the first release stands on.',
    groups: [
      {
        code: 'F1.1',
        name: 'Documentation and planning pack',
        items: [
          { code: 'F1.1.1', label: 'Looms × 10 — recorded walkthroughs', status: 'Not Started' },
          {
            code: 'F1.1.2',
            label: 'TRD — technical requirements document  done',
            status: 'Complete',
          },
          {
            code: 'F1.1.3',
            label: 'TRD Excel — requirements in tracked, tickable form',
            status: 'Not Started',
          },
          { code: 'F1.1.4', label: 'DFD — data flow diagrams, all levels', status: 'Not Started' },
          { code: 'F1.1.5', label: 'Product UI/UX and architecture', status: 'Not Started' },
          {
            code: 'F1.1.6',
            label: 'Five user journeys — Super Admin, Sponsor Admin, Sponsor Staff, Investor, Visitor',
            status: 'Not Started',
          },
          { code: 'F1.1.7', label: 'QA log  done', status: 'Complete' },
          { code: 'F1.1.8', label: 'Phase 1 to 6 PRD by hand', status: 'Not Started' },
          { code: 'F1.1.9', label: 'Mega PRD  done', status: 'Complete' },
          { code: 'F1.1.10', label: 'Cost Excel', status: 'Not Started' },
          { code: 'F1.1.11', label: 'By-hand PRD', status: 'Not Started' },
          { code: 'F1.1.12', label: 'Call notes  done', status: 'Complete' },
          {
            code: 'F1.1.13',
            label: 'Interviews on features — target 10–20 participants from live ad leads',
            status: 'Not Started',
          },
          { code: 'F1.1.14', label: 'User onboarding  done', status: 'Complete' },
          { code: 'F1.1.15', label: 'Market study and competition study', status: 'Not Started' },
          {
            code: 'F1.1.16',
            label: 'Feature prioritisation matrix — what is in Phase 1, what is deferred, what is excluded',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F1.2',
        name: 'Mock app features',
        items: [
          { code: 'F1.2.1', label: 'Login / signup', status: 'Not Started' },
          { code: 'F1.2.2', label: 'Google authentication  done', status: 'Complete' },
          {
            code: 'F1.2.3',
            label: 'Apple authentication',
            status: 'Not Started',
            notes: 'decide: needed now, or Phase 7 when the app store requires it',
          },
          { code: 'F1.2.4', label: 'Terms and legal acceptance screen', status: 'Not Started' },
          { code: 'F1.2.5', label: 'User onboarding and profile', status: 'Not Started' },
          { code: 'F1.2.6', label: 'Basic look and feel, initial UI/UX', status: 'Not Started' },
          {
            code: 'F1.2.7',
            label: 'Landing page linked to app — the handoff from marketing site into the product',
            status: 'Not Started',
          },
          {
            code: 'F1.2.8',
            label: 'LinkedIn import plugin — see §9, this one carries real risk',
            status: 'Not Started',
            notes: '*see §9, this one carries real risk',
          },
          {
            code: 'F1.2.9',
            label: 'Clickable prototype covering the full demo journey',
            status: 'Not Started',
          },
          {
            code: 'F1.2.10',
            label: 'Demo/sample data, clearly labelled as demo',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F1.3',
        name: 'Landing pages',
        items: [
          { code: 'F1.3.1', label: 'Home page', status: 'Not Started' },
          { code: 'F1.3.2', label: 'Pricing page', status: 'Not Started' },
          {
            code: 'F1.3.3',
            label: 'Third page',
            status: 'Not Started',
            notes: 'name it: intro-video page, post-payment walkthrough, or waitlist',
          },
          {
            code: 'F1.3.4',
            label: 'UTM capture and campaign attribution across all pages',
            status: 'Not Started',
          },
          { code: 'F1.3.5', label: 'Lead / waitlist capture form', status: 'Not Started' },
        ],
      },
      {
        code: 'F1.4',
        name: 'Legal documents',
        items: [
          {
            code: 'F1.4.1',
            label: 'Terms and Conditions — users',
            status: 'Not Started',
            notes: 'draft prepared',
          },
          { code: 'F1.4.2', label: 'Terms and Conditions — developers', status: 'Not Started' },
          { code: 'F1.4.3', label: 'NDA — users', status: 'Not Started' },
          { code: 'F1.4.4', label: 'NDA — developers', status: 'Not Started' },
          {
            code: 'F1.4.5',
            label: 'Privacy Policy',
            status: 'Not Started',
            notes: 'draft prepared — missing from the checklist, legally required',
          },
          {
            code: 'F1.4.6',
            label: 'Consent and opt-in wording',
            status: 'Not Started',
            notes: 'draft prepared — missing from the checklist, required before ads',
          },
          {
            code: 'F1.4.7',
            label: 'Investor acknowledgment and risk disclosure',
            status: 'Not Started',
            notes: 'draft prepared — missing from the checklist',
          },
          {
            code: 'F1.4.8',
            label: 'Cookie policy and consent banner',
            status: 'Not Started',
            notes: 'missing from the checklist',
          },
          {
            code: 'F1.4.9',
            label: 'Counsel review of all of the above before any live traffic',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F1.5',
        name: 'Commercial and advertising',
        items: [
          {
            code: 'F1.5.1',
            label: 'Ad #1 — free product launch, six-month run',
            status: 'Not Started',
          },
          { code: 'F1.5.2', label: 'Ad #2 — paid $25 entry', status: 'Not Started' },
          {
            code: 'F1.5.3',
            label: '$25 sign-up checkout, hosted, access granted only on successful payment',
            status: 'Not Started',
          },
          {
            code: 'F1.5.4',
            label: 'Funnel event instrumentation — view, CTA, registration started, registration completed, payment, login',
            status: 'Not Started',
          },
          {
            code: 'F1.5.5',
            label: 'Acceptance-ratio reporting — 10 clicks → 2 sign-ups; 10 leads → 5 calls → 2 buyers',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F1.6',
        name: 'Foundation',
        items: [
          {
            code: 'F1.6.1',
            label: 'Repository, environments, CI, deployment, SSL',
            status: 'Not Started',
          },
          {
            code: 'F1.6.2',
            label: 'Role model — five roles, enforced server-side',
            status: 'Not Started',
          },
          {
            code: 'F1.6.3',
            label: 'Tenant isolation rules at the data layer',
            status: 'Not Started',
          },
          {
            code: 'F1.6.4',
            label: 'Draft ERD',
            status: 'Not Started',
            notes: 'needed here, not Phase 3, or Phase 2 data will need migrating',
          },
          { code: 'F1.6.5', label: 'Error monitoring and logging', status: 'Not Started' },
          {
            code: 'F1.6.6',
            label: 'QA pass and written Phase 1 acceptance',
            status: 'Not Started',
          },
        ],
      },
    ],
  },
  {
    n: 2,
    name: 'CRM, Profiles and Networking',
    icon: 'contacts',
    avatar: 'a2',
    blurb:
      'Contacts and pipelines, investor, developer and company profiles, communities and the forum, plus Stripe subscription billing and the notifications around it.',
    groups: [
      {
        code: 'F2.1',
        name: 'CRM',
        items: [
          {
            code: 'F2.1.1',
            label: 'Contacts — create, edit, delete, search, filter',
            status: 'Not Started',
          },
          {
            code: 'F2.1.2',
            label: 'Pipelines — default investor-outreach stages',
            status: 'Not Started',
          },
          {
            code: 'F2.1.3',
            label: 'Custom pipeline stages',
            status: 'Not Started',
            notes: 'decide: here or Phase 7',
          },
          {
            code: 'F2.1.4',
            label: 'Lead and interest capture, linked to deal and company',
            status: 'Not Started',
          },
          { code: 'F2.1.5', label: 'Notes, activity log and timeline', status: 'Not Started' },
          { code: 'F2.1.6', label: 'Contact import and export (CSV)', status: 'Not Started' },
          {
            code: 'F2.1.7',
            label: 'Gmail connect — outreach sync',
            status: 'Not Started',
            notes: 'deprioritised within Phase 2; confirm it stays',
          },
        ],
      },
      {
        code: 'F2.2',
        name: 'Profiles',
        items: [
          { code: 'F2.2.1', label: 'Investor profiles', status: 'Not Started' },
          {
            code: 'F2.2.2',
            label: 'Developer / real-estate professional profiles',
            status: 'Not Started',
          },
          { code: 'F2.2.3', label: 'Company profiles', status: 'Not Started' },
          {
            code: 'F2.2.4',
            label: 'Team member management and role assignment',
            status: 'Not Started',
          },
          { code: 'F2.2.5', label: 'Seat counting, reported to billing', status: 'Not Started' },
        ],
      },
      {
        code: 'F2.3',
        name: 'Communities and networking',
        items: [
          { code: 'F2.3.1', label: 'Groups / communities', status: 'Not Started' },
          { code: 'F2.3.2', label: 'Investor groups', status: 'Not Started' },
          {
            code: 'F2.3.3',
            label: 'Industry and location-based communities',
            status: 'Not Started',
          },
          { code: 'F2.3.4', label: 'Community admin page', status: 'Not Started' },
          { code: 'F2.3.5', label: 'Community profile page', status: 'Not Started' },
          { code: 'F2.3.6', label: 'Posts and discussions — the forum', status: 'Not Started' },
          {
            code: 'F2.3.7',
            label: 'Networking member directory, filterable',
            status: 'Not Started',
          },
          {
            code: 'F2.3.8',
            label: 'Chat / direct messaging',
            status: 'Not Started',
            notes: 'decide: Phase 2 or later. Adds moderation and abuse-reporting obligations',
          },
          { code: 'F2.3.9', label: 'Moderation and content flagging', status: 'Not Started' },
        ],
      },
      {
        code: 'F2.4',
        name: 'Investor area',
        items: [
          {
            code: 'F2.4.1',
            label: 'Investor dashboard — saved interests, recent activity',
            status: 'Not Started',
          },
          {
            code: 'F2.4.2',
            label: 'Expressions of interest and their status',
            status: 'Not Started',
          },
          { code: 'F2.4.3', label: 'Following sponsors or markets', status: 'Not Started' },
        ],
      },
      {
        code: 'F2.5',
        name: 'Monetisation',
        items: [
          {
            code: 'F2.5.1',
            label: 'Stripe subscription billing — create, upgrade, downgrade, cancel, proration',
            status: 'Not Started',
          },
          {
            code: 'F2.5.2',
            label: 'Pricing tiers and server-side entitlement enforcement',
            status: 'Not Started',
          },
          {
            code: 'F2.5.3',
            label: 'Storage add-on packs ("space add") and metered quota',
            status: 'Not Started',
          },
          {
            code: 'F2.5.4',
            label: 'Billing portal, invoices, receipts, dunning',
            status: 'Not Started',
          },
          { code: 'F2.5.5', label: 'Tax handling', status: 'Not Started' },
          {
            code: 'F2.5.6',
            label: 'Trial or free-tier logic, if Ad #1 runs a free product',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F2.6',
        name: 'Supporting',
        items: [
          { code: 'F2.6.1', label: 'In-app notifications', status: 'Not Started' },
          { code: 'F2.6.2', label: 'Transactional email', status: 'Not Started' },
          {
            code: 'F2.6.3',
            label: 'Notification preferences and unsubscribe',
            status: 'Not Started',
          },
          {
            code: 'F2.6.4',
            label: 'Niche news and market analysis feed',
            status: 'Not Started',
            notes: 'decide: curated editorial (cheap, Phase 2) or data-driven (Phase 4)',
          },
        ],
      },
    ],
  },
  {
    n: 3,
    name: 'Data Room and Basic Underwriting',
    icon: 'dataroom',
    avatar: 'a3',
    blurb:
      'Permissioned document storage on R2, the first underwriting sandbox, deal records and discovery, field-visibility controls and the LP cap table.',
    groups: [
      {
        code: 'F3.1',
        name: 'Data room',
        items: [
          {
            code: 'F3.1.1',
            label: 'Upload — Excel, PowerPoint, PDF, property and deal documents',
            status: 'Not Started',
          },
          {
            code: 'F3.1.2',
            label: 'Folder structure and document organisation',
            status: 'Not Started',
          },
          {
            code: 'F3.1.3',
            label: 'Access control — invitation and password-protected access',
            status: 'Not Started',
          },
          {
            code: 'F3.1.4',
            label: 'Token-based temporary URLs, time-limited',
            status: 'Not Started',
          },
          { code: 'F3.1.5', label: 'Secure cloud storage on Cloudflare R2', status: 'Not Started' },
          {
            code: 'F3.1.6',
            label: 'Document access log — who opened what, when, for how long',
            status: 'Not Started',
          },
          {
            code: 'F3.1.7',
            label: 'Confidentiality undertaking before first access',
            status: 'Not Started',
          },
          {
            code: 'F3.1.8',
            label: 'Versioning and replacement of documents',
            status: 'Not Started',
          },
          {
            code: 'F3.1.9',
            label: 'Retention, archive and verified deletion',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F3.2',
        name: 'Basic underwriting sandbox',
        items: [
          {
            code: 'F3.2.1',
            label: 'Deal input templates — structured, constrained fields',
            status: 'Not Started',
          },
          { code: 'F3.2.2', label: 'Cap rate, NOI, DSCR calculations', status: 'Not Started' },
          { code: 'F3.2.3', label: 'Excel output export', status: 'Not Started' },
          {
            code: 'F3.2.4',
            label: 'Saved assumptions, reusable per sponsor',
            status: 'Not Started',
          },
          {
            code: 'F3.2.5',
            label: 'Custom format upload with column-mapping wizard',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F3.3',
        name: 'Deals and discovery',
        items: [
          {
            code: 'F3.3.1',
            label: 'Deal record and lifecycle states',
            status: 'Not Started',
            notes: 'timestamps here are the only source of deal velocity in Phase 4',
          },
          { code: 'F3.3.2', label: 'Deal creation wizard', status: 'Not Started' },
          {
            code: 'F3.3.3',
            label: 'Shared map with approximate public location',
            status: 'Not Started',
          },
          { code: 'F3.3.4', label: 'Search and filtering', status: 'Not Started' },
          { code: 'F3.3.5', label: 'Acquisition and cap-rate input fields', status: 'Not Started' },
        ],
      },
      {
        code: 'F3.4',
        name: 'Public and semi-public area',
        items: [
          {
            code: 'F3.4.1',
            label: 'Field-visibility policy engine — public / gated / private per field',
            status: 'Not Started',
          },
          { code: 'F3.4.2', label: 'Public aggregate statistics', status: 'Not Started' },
          { code: 'F3.4.3', label: 'Anonymity thresholds and banding', status: 'Not Started' },
          {
            code: 'F3.4.4',
            label: 'Sponsor opt-in controls for location and figures',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F3.5',
        name: 'Capital structure',
        items: [
          {
            code: 'F3.5.1',
            label: 'LP cap table — commitments, contributions, units, ownership',
            status: 'Not Started',
          },
          {
            code: 'F3.5.2',
            label: 'Waterfall structure — pref, catch-up, promote, splits',
            status: 'Not Started',
          },
          {
            code: 'F3.5.3',
            label: 'Scenario illustration only — no payable distribution figures',
            status: 'Not Started',
            notes: '*no payable distribution figures',
          },
        ],
      },
    ],
  },
  {
    n: 4,
    name: 'Advanced Underwriting and Analytics',
    icon: 'analytics',
    avatar: 'a4',
    blurb:
      'Structured underwriting data turned into IRR, sensitivity and benchmarks — with sponsor dashboards, exports, a data classification policy and a bring-your-own AI plugin.',
    groups: [
      {
        code: 'F4.1',
        name: 'Structured data and analytics foundation',
        items: [
          {
            code: 'F4.1.1',
            label: 'Structured storage of underwriting data',
            status: 'Not Started',
          },
          { code: 'F4.1.2', label: 'Analysis and aggregation layer', status: 'Not Started' },
          {
            code: 'F4.1.3',
            label: 'Deal velocity and acquisition-speed metrics',
            status: 'Not Started',
          },
          { code: 'F4.1.4', label: 'Area, range and market aggregates', status: 'Not Started' },
        ],
      },
      {
        code: 'F4.2',
        name: 'Advanced underwriting',
        items: [
          { code: 'F4.2.1', label: 'Versioned canonical templates', status: 'Not Started' },
          { code: 'F4.2.2', label: 'IRR, equity multiple, cash-on-cash', status: 'Not Started' },
          { code: 'F4.2.3', label: 'Sensitivity analysis', status: 'Not Started' },
          { code: 'F4.2.4', label: 'Underwriting insights and flags', status: 'Not Started' },
        ],
      },
      {
        code: 'F4.3',
        name: 'Dashboards and reporting',
        items: [
          {
            code: 'F4.3.1',
            label: 'Sponsor analytics dashboard — views, unique viewers, drop-off, source, document opens',
            status: 'Not Started',
          },
          { code: 'F4.3.2', label: 'Platform analytics dashboard', status: 'Not Started' },
          {
            code: 'F4.3.3',
            label: 'Benchmark view — your deal versus the submarket',
            status: 'Not Started',
          },
          {
            code: 'F4.3.4',
            label: 'Developer ranking — activity-based, private first',
            status: 'Not Started',
          },
          { code: 'F4.3.5', label: 'Reports and exports, PDF and CSV', status: 'Not Started' },
          {
            code: 'F4.3.6',
            label: 'Advertising and funnel dashboard, replacing the manual sales sheet',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F4.4',
        name: 'Data classification — public / private / internal',
        items: [
          {
            code: 'F4.4.1',
            label: 'Public data — property counts, unit counts, general developer information, aggregated statistics, market cap rates',
            status: 'Not Started',
          },
          {
            code: 'F4.4.2',
            label: 'Private user and deal data — specific property detail, current deals, location, loan detail, investor information, financial terms',
            status: 'Not Started',
          },
          {
            code: 'F4.4.3',
            label: 'Internal company analytics — data retained by the operator for its own business intelligence. This is a legal decision, not a technical one. It must be disclosed in the Privacy Policy, it may require an opt-out, and sponsors will ask about it directly. Settle it before Phase 3 ships, because Phase 3 is when the data starts accumulating.',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F4.5',
        name: 'Bring-your-own AI plugin',
        items: [
          {
            code: 'F4.5.1',
            label: 'Connect your own ChatGPT or equivalent account',
            status: 'Not Started',
          },
          {
            code: 'F4.5.2',
            label: 'Encrypted per-tenant credential vault, revocable',
            status: 'Not Started',
          },
          { code: 'F4.5.3', label: 'AI financial modelling assistant', status: 'Not Started' },
          { code: 'F4.5.4', label: 'AI deck and document drafting', status: 'Not Started' },
          {
            code: 'F4.5.5',
            label: 'Output labelled assistive, review required before use',
            status: 'Not Started',
          },
          { code: 'F4.5.6', label: 'Usage metering and cost visibility', status: 'Not Started' },
        ],
      },
    ],
  },
  {
    n: 5,
    name: 'AI Agent and Regulatory / Cyber',
    icon: 'bolt',
    avatar: 'a5',
    blurb:
      'An in-product assistant over permitted data, personalised recommendations, spend caps and admin controls, and the regulatory and cyber work that has to go with them.',
    groups: [
      {
        code: 'F5.1',
        name: 'Platform AI agent',
        items: [
          {
            code: 'F5.1.1',
            label: 'In-product assistant over permitted data',
            status: 'Not Started',
          },
          {
            code: 'F5.1.2',
            label: 'Search, summarise, suggest next action',
            status: 'Not Started',
          },
          { code: 'F5.1.3', label: 'Strict tenant-boundary enforcement', status: 'Not Started' },
          {
            code: 'F5.1.4',
            label: 'Full audit log — who asked, what data was in scope, cost',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F5.2',
        name: 'Intelligence layer',
        items: [
          {
            code: 'F5.2.1',
            label: 'Intent and preference signals, including dislikes, with consent',
            status: 'Not Started',
          },
          { code: 'F5.2.2', label: 'Personalised recommendations', status: 'Not Started' },
          { code: 'F5.2.3', label: 'Explainability and user opt-out', status: 'Not Started' },
        ],
      },
      {
        code: 'F5.3',
        name: 'Controls',
        items: [
          { code: 'F5.3.1', label: 'Usage limits, spend caps, throttling', status: 'Not Started' },
          { code: 'F5.3.2', label: 'Administrator controls and alerts', status: 'Not Started' },
          { code: 'F5.3.3', label: 'Disclaimers on every AI surface', status: 'Not Started' },
        ],
      },
      {
        code: 'F5.4',
        name: 'Regulatory and cyber',
        items: [
          { code: 'F5.4.1', label: 'Security hardening', status: 'Not Started' },
          {
            code: 'F5.4.2',
            label: 'Regulatory review of AI outputs and data use',
            status: 'Not Started',
          },
          { code: 'F5.4.3', label: 'Penetration test preparation', status: 'Not Started' },
        ],
      },
    ],
  },
  {
    n: 6,
    name: 'Stabilisation, Native Planning, Interview, Team',
    icon: 'lock',
    avatar: 'a6',
    blurb:
      'Defect burn-down, disaster recovery and incident response, the native rebuild and data migration, SOC 2 readiness and independent testing, then hiring and planning.',
    groups: [
      {
        code: 'F6.1',
        name: 'Stabilisation',
        items: [
          { code: 'F6.1.1', label: 'Defect burn-down and performance work', status: 'Not Started' },
          {
            code: 'F6.1.2',
            label: 'Backup, disaster recovery, restore testing',
            status: 'Not Started',
          },
          { code: 'F6.1.3', label: 'Incident response procedure', status: 'Not Started' },
        ],
      },
      {
        code: 'F6.2',
        name: 'Native migration',
        items: [
          {
            code: 'F6.2.1',
            label: 'Native rebuild of core application and data model',
            status: 'Not Started',
          },
          {
            code: 'F6.2.2',
            label: 'Data migration with verification and rollback',
            status: 'Not Started',
          },
          {
            code: 'F6.2.3',
            label: 'Deferred custom capability — public API, fine-grained permissions, scheduled aggregation, heavy file parsing',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F6.3',
        name: 'Compliance',
        items: [
          {
            code: 'F6.3.1',
            label: 'SOC 2 readiness, control matrix and evidence pack',
            status: 'Not Started',
          },
          {
            code: 'F6.3.2',
            label: 'Independent penetration test and remediation',
            status: 'Not Started',
          },
          { code: 'F6.3.3', label: 'Insurance — technology E&O and cyber', status: 'Not Started' },
          {
            code: 'F6.3.4',
            label: 'Data retention, export and privacy workflows',
            status: 'Not Started',
          },
        ],
      },
      {
        code: 'F6.4',
        name: 'Product and team',
        items: [
          { code: 'F6.4.1', label: 'New product interview round', status: 'Not Started' },
          { code: 'F6.4.2', label: 'Team planning and hiring', status: 'Not Started' },
          { code: 'F6.4.3', label: 'Native app planning', status: 'Not Started' },
        ],
      },
    ],
  },
  {
    n: 7,
    name: 'Native App and New Features',
    icon: 'phone',
    avatar: 'a7',
    blurb:
      'iOS and Android build, test and release with push notifications, the deferred custom dashboards, fields and reports, and the governance that controls what ships next.',
    groups: [
      {
        code: 'F7.1',
        name: 'Native application',
        items: [
          { code: 'F7.1.1', label: 'Native app PRD', status: 'Not Started' },
          {
            code: 'F7.1.2',
            label: 'Native prototype for priority journeys',
            status: 'Not Started',
          },
          {
            code: 'F7.1.3',
            label: 'iOS and Android build, test, submission and release',
            status: 'Not Started',
          },
          { code: 'F7.1.4', label: 'Push notifications', status: 'Not Started' },
          {
            code: 'F7.1.5',
            label: 'Sign in with Apple',
            status: 'Not Started',
            notes: 'required by the app store if other social logins are offered',
          },
        ],
      },
      {
        code: 'F7.2',
        name: 'Deferred custom features',
        items: [
          { code: 'F7.2.1', label: 'Custom dashboard builder', status: 'Not Started' },
          {
            code: 'F7.2.2',
            label: 'Per-tenant custom fields and custom roles',
            status: 'Not Started',
          },
          { code: 'F7.2.3', label: 'Per-tenant configurable reports', status: 'Not Started' },
        ],
      },
      {
        code: 'F7.3',
        name: 'Governance',
        items: [
          {
            code: 'F7.3.1',
            label: 'Feature intake, sizing and approval workflow',
            status: 'Not Started',
          },
          { code: 'F7.3.2', label: 'Change control and roadmap review', status: 'Not Started' },
        ],
      },
    ],
  },
]

/** How many features a phase contains, across all of its groups. */
export function phaseItemCount(phase) {
  return phase.groups.reduce((count, group) => count + group.items.length, 0)
}
