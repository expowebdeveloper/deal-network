/**
 * The two public legal documents, rendered by components/landing/Legal.jsx at
 * /privacy and /terms and linked from the footer of every public page.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * DRAFT. These are written to describe what the platform actually does — OAuth
 * sign-in, the Gmail sync, the data room, bring-your-own-AI-key underwriting,
 * and the retention position already summarised in data/onboarding.js — but
 * they have NOT been reviewed by a lawyer. Before launch:
 *
 *   1. Have a qualified adviser review both documents for your jurisdiction.
 *   2. Fill in `legalMeta` below — registered entity, address, contact
 *      addresses and governing law are placeholders.
 *   3. Re-check every factual claim against what the platform does at the time
 *      (sub-processors, transfers, retention periods, payment provider).
 * ─────────────────────────────────────────────────────────────────────────────
 */

/** TODO: replace every value here with the real company details before launch. */
export const legalMeta = {
  company: 'Deal Network',
  entity: '[Registered company name and number]',
  address: '[Registered office address]',
  privacyEmail: 'privacy@dealnetwork.example',
  legalEmail: 'legal@dealnetwork.example',
  governingLaw: '[Governing law and courts]',
  updated: '14 August 2026',
}

export const privacyPolicy = {
  id: 'privacy',
  title: 'Privacy Policy',
  intro:
    'This policy explains what information Deal Network collects about you, why we hold it, who can see it and what you can do about it. It covers the website, the platform and every module in it.',
  sections: [
    {
      h: 'Who we are',
      p: [
        `${legalMeta.company} (${legalMeta.entity}, ${legalMeta.address}) is the controller of the personal information described in this policy.`,
        `For anything in this document, including a request about your own data, write to ${legalMeta.privacyEmail}.`,
      ],
    },
    {
      h: 'What we collect',
      p: ['We collect the following, and nothing is bought from a data broker:'],
      list: [
        'Account details — your name, email address and profile picture, passed to us by Google or Apple when you sign in.',
        'Profile details — your role, company, markets, asset classes and anything else you choose to add to your profile.',
        'Content you publish — posts, comments, community activity and the communities you create or join.',
        'Contacts and pipeline data — the contacts, deals and notes you add to the CRM, and the email threads synced from a connected inbox.',
        'Files you upload — documents, models and property information placed in a data room, plus the access you grant over them.',
        'Payment records — plan, billing status and invoice history. Card details are handled by our payment provider; we never see or store the card number.',
        'Technical data — IP address, device and browser, timestamps and the pages and actions taken in the platform, kept in server logs.',
      ],
    },
    {
      h: 'Where it comes from',
      p: [
        'Most of it comes from you, directly. The rest comes from your sign-in provider (Google or Apple), from an inbox you choose to connect, from our payment provider, and occasionally from other members — for example when someone adds you to their contacts or invites you to a data room.',
      ],
    },
    {
      h: 'Why we use it, and on what basis',
      p: ['We use your information to:'],
      list: [
        'Provide the service you signed up for — your account, profile, communities, CRM, data rooms and analytics (basis: performance of our contract with you).',
        'Take payment and manage your plan (basis: contract, and legal obligation for tax and accounting records).',
        'Keep the platform safe — preventing fraud, abuse, spam and unauthorised access (basis: our legitimate interest in a working, trustworthy network).',
        'Support you when you ask, and answer the questions you send us (basis: contract and legitimate interest).',
        'Improve the product using aggregate usage patterns (basis: legitimate interest; we use aggregate figures wherever they will do the job).',
        'Send product updates and announcements, where you opted in (basis: consent — withdraw it any time from your profile or the footer of the email).',
        'Meet legal obligations and respond to lawful requests (basis: legal obligation).',
      ],
    },
    {
      h: 'Connected inboxes',
      p: [
        'Connecting Gmail is optional. If you do, we sync the contacts and message metadata the CRM needs so you are not re-typing the same information into a second system, and we hold that data under the same terms as everything else here.',
        'We do not use the content of a connected inbox for advertising, we do not sell it, and we do not use it to build profiles of the people you correspond with beyond the CRM records you can see and delete. You can disconnect the inbox at any time from your profile; disconnecting stops any further sync.',
      ],
    },
    {
      h: 'AI features',
      p: [
        'AI underwriting runs on an AI provider account you connect with your own key. When you run a model, the deal information you submit is sent to that provider and their privacy terms apply to that processing — read them before you connect a key.',
        'We do not use your deal information, documents or content to train our own models, and we do not pass them to an AI provider except when you ask us to run something.',
      ],
    },
    {
      h: 'Who can see your information',
      p: [
        'You decide, field by field, whether each part of your profile is public, visible to members only, or private. Content you post in a community is visible to that community. Documents in a data room are visible only to the parties you provision, through links that can expire.',
        'Internally, access is limited to the people who need it to run and support the service. Externally, we use service providers who process data on our instructions — hosting and storage, email delivery, payment processing, error monitoring and analytics — under contracts that hold them to this policy.',
      ],
    },
    {
      h: 'What we do not do',
      p: [
        'We do not sell your personal information. We do not share it for someone else’s advertising. We disclose it outside the categories above only where the law requires it, where it is necessary to protect the rights or safety of members or the public, or where the business is transferred — in which case you will be told before your data moves.',
      ],
    },
    {
      h: 'International transfers',
      p: [
        'Our providers may store or process data outside your country. Where that happens, the transfer is covered by an approved safeguard — standard contractual clauses or an adequacy decision — and you can ask us for details.',
      ],
    },
    {
      h: 'How long we keep it',
      p: [
        'Information you add is retained for as long as your account exists and for a defined period after you close it; it is not deleted automatically the moment you stop using the platform. We keep what we must for tax, accounting and dispute-resolution purposes, and backups clear on their own retention cycle.',
        'You can ask us to delete your account and content earlier — see your rights below.',
      ],
    },
    {
      h: 'Security',
      p: [
        'Sign-in is OAuth only, so there is no password of yours for us to lose. Data is encrypted in transit and at rest, document access is permissioned per party, and external share links are token-based and expiring.',
        'No platform can promise absolute security. If a breach affects your information, we will tell you and the relevant regulator as the law requires.',
      ],
    },
    {
      h: 'Your rights',
      p: [
        'Depending on where you live, you can ask us to give you a copy of your data, correct it, delete it, export it in a portable format, restrict or object to a particular use, or withdraw a consent you gave earlier. Ask at the address above and we will respond within the period the law allows.',
        'If you think we have handled your information badly, tell us first — but you are entitled to complain to your local data protection authority either way.',
      ],
    },
    {
      h: 'Cookies and local storage',
      p: [
        'We use storage in your browser to keep you signed in and to remember your preferences. We do not run third-party advertising trackers. Blocking this storage will sign you out and break parts of the platform.',
      ],
    },
    {
      h: 'Children',
      p: [
        'Deal Network is a business platform for adults. It is not intended for anyone under 18, and we do not knowingly collect information from them.',
      ],
    },
    {
      h: 'Changes to this policy',
      p: [
        'When this policy changes, we update the date at the top and, for anything material, tell members directly before it takes effect.',
      ],
    },
  ],
}

export const termsConditions = {
  id: 'terms',
  title: 'Terms & Conditions',
  intro:
    'These terms are the agreement between you and Deal Network. By creating an account or using the platform you accept them, so read them before you sign up.',
  sections: [
    {
      h: 'Who can use Deal Network',
      p: [
        'You must be 18 or over and using the platform for business purposes. Early access is invitation and referral only, and we may decline or withdraw access at our discretion.',
        'The information you publish about yourself and your company must be accurate. Impersonating a person, a firm or a mandate you do not hold is grounds for immediate removal.',
      ],
    },
    {
      h: 'Your account',
      p: [
        'You sign in with Google or Apple. Keep that account secure — anything done through your sign-in is treated as done by you, and you must tell us promptly if you think someone else has access.',
        'An account belongs to one person. Team members get their own accounts and seats, with the roles and permissions your plan allows; do not share a login.',
      ],
    },
    {
      h: 'Plans, payment and early access',
      p: [
        'Early access is free and does not require a card. Paid tiers are billed in advance through our payment provider at the price shown when you subscribe, plus any applicable tax.',
        'You can change or cancel your plan at any time; cancellation takes effect at the end of the period you have paid for, and we do not give partial refunds for time already run unless the law requires it. If we change prices, existing subscribers get notice before the change applies to them.',
      ],
    },
    {
      h: 'What you may post',
      p: ['You are responsible for everything you upload, publish or send. You must not:'],
      list: [
        'Post anything unlawful, defamatory, discriminatory, misleading or infringing someone else’s rights.',
        'Misrepresent a property, a project, a mandate, a track record or the terms of a deal.',
        'Upload material you do not have the right to share, including confidential information belonging to a client or employer.',
        'Send bulk unsolicited messages, or use member contact details for anything other than a genuine approach about the platform’s subject matter.',
        'Scrape, harvest or bulk-export member data, or attempt to work around access controls, rate limits or permissions.',
        'Upload malware, or interfere with the platform’s operation or security.',
      ],
    },
    {
      h: 'Member content is not verified',
      p: [
        'This one matters. We do not verify, audit, endorse or guarantee any information a member publishes about themselves, a property, a project or a deal — including numbers, valuations, track records, planning status and ownership.',
        'The platform is an introduction and a workspace, not diligence. Anything you rely on, you check yourself, with your own advisers. Any transaction you enter into with another member is between you and them, and we are not a party to it, not an agent for either side, and not a broker.',
      ],
    },
    {
      h: 'Not financial, legal or investment advice',
      p: [
        'Market data, benchmarks, analytics, cap rate figures and underwriting outputs are tools and estimates, generated from the inputs given to them. They are not advice, not a valuation, and not a recommendation to buy, sell, lend or invest.',
        'Decisions you make with them are yours, and you should take professional advice before committing to a transaction.',
      ],
    },
    {
      h: 'Data rooms and sharing',
      p: [
        'You control who you provision into a data room and what you share with them. You confirm you have the right to upload and share what you put there, and that doing so does not breach a confidentiality obligation you owe to someone else.',
        'Expiring links and permissions limit access; they cannot stop a person who has legitimately been given a file from keeping a copy. Share accordingly.',
      ],
    },
    {
      h: 'Connected services and AI keys',
      p: [
        'Connecting an inbox or an AI provider brings that provider’s terms into play alongside these. You are responsible for holding a valid account with them, for keeping your key secure, and for any usage cost they charge you.',
        'We supply the templates, formulas and outputs; we do not control the AI provider’s model, availability or results, and outputs should be reviewed by a human before they leave your desk.',
      ],
    },
    {
      h: 'Who owns what',
      p: [
        'The platform, its software, design and content are ours and stay ours. You get a personal, non-exclusive, non-transferable right to use it while your account is in good standing.',
        'What you upload stays yours. You grant us the licence we need to host, store, back up, display and transmit it in order to run the service and to show it to the people you have chosen to show it to — nothing wider than that.',
      ],
    },
    {
      h: 'Availability and changes',
      p: [
        'Deal Network is being built in phases, and the roadmap describes what we intend to ship, not a promise that a given feature will arrive on a given date or in a given form. Features may change, and modules in early phases may be rough.',
        'We aim to keep the service available but do not guarantee uninterrupted access. Maintenance, provider outages and things outside our control happen; we will give notice of planned downtime where we can.',
      ],
    },
    {
      h: 'Suspension and closing your account',
      p: [
        'We may suspend or close an account that breaches these terms, that puts other members or the platform at risk, or where we are required to by law. Where it is reasonable, we will tell you why and give you a chance to put it right.',
        'You can close your account whenever you want. Closing it removes your access; retention of what you had stored follows the Privacy Policy.',
      ],
    },
    {
      h: 'Liability',
      p: [
        'Nothing here limits liability that cannot be limited by law — including for death or personal injury caused by negligence, or for fraud.',
        'Subject to that: the platform is provided as it is, we exclude implied warranties to the extent the law allows, and we are not liable for lost profits, lost opportunities, lost deals, loss of data, or indirect or consequential loss. Our total liability in any twelve-month period is capped at the fees you paid us in that period.',
        'We are not liable for the acts, omissions, statements or solvency of another member.',
      ],
    },
    {
      h: 'Indemnity',
      p: [
        'If a third party brings a claim against us because of what you posted, uploaded, shared or did on the platform, or because you broke these terms, you will cover the reasonable costs and damages that result.',
      ],
    },
    {
      h: 'Governing law and disputes',
      p: [
        `These terms are governed by ${legalMeta.governingLaw}, and that is where disputes are heard. If you are a consumer, this does not remove protections you have under the law of the country you live in.`,
        `Before anything formal, write to ${legalMeta.legalEmail} — most things are quicker to fix that way.`,
      ],
    },
    {
      h: 'Changes to these terms',
      p: [
        'We update these terms as the platform grows. The date at the top shows the current version, and we tell members about material changes before they take effect. Continuing to use the platform after that means you accept the new version.',
      ],
    },
  ],
}

export const legalDocs = { privacy: privacyPolicy, terms: termsConditions }
