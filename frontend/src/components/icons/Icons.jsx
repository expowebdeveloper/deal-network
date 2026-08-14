/* Every SVG used across the app, one component each.
   Stroke icons share a base so weights stay consistent. */

function Stroke({ width = 2, children, ...rest }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={width} {...rest}>
      {children}
    </svg>
  )
}

/**
 * The mark: a lime tile with the house cut in deep green.
 *
 * Lime is the palette's highlight, and this is the one thing on screen that has
 * to read on the light page and on the dark green sidebar alike — the glyph
 * sits at 11:1 on the tile either way.
 */
export function BrandMark(props) {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" fill="none" {...props}>
      <rect width="32" height="32" rx="8" fill="var(--lime,#A3E635)" />
      <path d="M8 21V13.4L16 8l8 5.4V21" stroke="var(--on-lime,#06231A)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13 21v-4.6h6V21" stroke="var(--on-lime,#06231A)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="16" cy="12.6" r="1.5" fill="var(--on-lime,#06231A)" />
    </svg>
  )
}

/* --- Navigation --- */
export const HomeIcon = (p) => (
  <Stroke width={1.9} {...p}><path d="M3 10.2 12 3l9 7.2V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z" /></Stroke>
)
export const CommunitiesIcon = (p) => (
  <Stroke width={1.9} {...p}>
    <circle cx="9" cy="8" r="3.2" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
    <circle cx="17.5" cy="9.5" r="2.4" /><path d="M16 15.6a5.6 5.6 0 0 1 5.5 4.4" />
  </Stroke>
)
export const SearchIcon = (p) => (
  <Stroke width={1.9} {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></Stroke>
)
export const InvestorsIcon = (p) => (
  <Stroke width={1.9} {...p}><path d="M3 17.5 9 11l4 4 8-8.5" /><path d="M15 6.5h6v6" /></Stroke>
)
export const ContactsIcon = (p) => (
  <Stroke width={1.9} {...p}>
    <rect x="3.5" y="4" width="17" height="16" rx="2.2" /><path d="M8 4v16M11.5 9.5h5M11.5 14h3" />
  </Stroke>
)
export const PlansIcon = (p) => (
  <Stroke width={1.9} {...p}><rect x="2.5" y="5.5" width="19" height="13" rx="2.2" /><path d="M2.5 10h19" /></Stroke>
)
export const LockIcon = (p) => (
  <Stroke width={1.9} {...p}><rect x="4" y="10.5" width="16" height="10" rx="2" /><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" /></Stroke>
)
export const UnderwritingIcon = (p) => (
  <Stroke width={1.9} {...p}><rect x="3.5" y="3.5" width="17" height="17" rx="2.2" /><path d="M8 8h8M8 12h8M8 16h4" /></Stroke>
)
export const ProfileIcon = (p) => (
  <Stroke width={1.9} {...p}><circle cx="12" cy="8" r="3.6" /><path d="M4.5 20a7.5 7.5 0 0 1 15 0" /></Stroke>
)

/* --- Topbar --- */
export const FlowIcon = (p) => (
  <Stroke {...p}>
    <rect x="3" y="3" width="7" height="5" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" />
    <rect x="8.5" y="16" width="7" height="5" rx="1" /><path d="M6.5 8v3.5h11V8M12 11.5V16" />
  </Stroke>
)
export const BellIcon = (p) => (
  <Stroke width={1.9} {...p}>
    <path d="M18 8.5a6 6 0 1 0-12 0c0 6-2.5 7.5-2.5 7.5h17S18 14.5 18 8.5" /><path d="M13.7 20a2 2 0 0 1-3.4 0" />
  </Stroke>
)
export const PresenterIcon = (p) => (
  <Stroke width={1.9} {...p}><path d="M4 4.5h16v12H13l-4 3.5v-3.5H4z" /><path d="M8 9h8M8 12.5h5" /></Stroke>
)

/* --- Feed --- */
export const PhotoIcon = (p) => (
  <Stroke width={1.9} {...p}>
    <rect x="3" y="4.5" width="18" height="15" rx="2" /><circle cx="8.5" cy="10" r="1.8" /><path d="m3 16 5-4 4 3 4-3.5 5 4.5" />
  </Stroke>
)
export const DocumentIcon = (p) => (
  <Stroke width={1.9} {...p}>
    <path d="M13 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9z" /><path d="M13 3v6h6" />
  </Stroke>
)
export const PinIcon = (p) => (
  <Stroke width={1.9} {...p}><circle cx="12" cy="10" r="3" /><path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11" /></Stroke>
)
export const LikeIcon = (p) => (
  <Stroke width={1.9} {...p}><path d="M7 20V10L12 3l1 1v6h6.5a2 2 0 0 1 2 2.3l-1.2 6a2 2 0 0 1-2 1.7z" /></Stroke>
)
export const CommentIcon = (p) => (
  <Stroke width={1.9} {...p}><path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l.9-4.4A8 8 0 1 1 20 12" /></Stroke>
)
export const ShareIcon = (p) => (
  <Stroke width={1.9} {...p}><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7" /><path d="M16 6l-4-4-4 4M12 2v13" /></Stroke>
)

/* --- Generic --- */
export const PlusIcon = (p) => <Stroke width={2.2} {...p}><path d="M12 5v14M5 12h14" /></Stroke>
export const CheckIcon = (p) => <Stroke width={2.4} {...p}><path d="m5 12.5 4.5 4.5L19 7.5" /></Stroke>
export const CrossIcon = (p) => <Stroke width={2.4} {...p}><path d="M6 6l12 12M18 6 6 18" /></Stroke>
export const CloseIcon = (p) => <Stroke {...p}><path d="M6 6l12 12M18 6 6 18" /></Stroke>
export const InfoIcon = (p) => <Stroke {...p}><circle cx="12" cy="12" r="9.5" /><path d="M12 8v5M12 16h.01" /></Stroke>
export const GlobeIcon = (p) => (
  <Stroke {...p}>
    <circle cx="12" cy="12" r="9.5" /><path d="M2.5 12h19M12 2.5a15 15 0 0 1 0 19 15 15 0 0 1 0-19" />
  </Stroke>
)
export const DragIcon = (p) => (
  <Stroke {...p}><path d="M9 5h.01M9 12h.01M9 19h.01M15 5h.01M15 12h.01M15 19h.01" /></Stroke>
)
export const ArrowRightIcon = (p) => <Stroke {...p}><path d="M4 12h15M14 7l5 5-5 5" /></Stroke>
export const ArrowDownIcon = (p) => <Stroke {...p}><path d="M12 4v15M7 14l5 5 5-5" /></Stroke>

/* --- OAuth --- */
export function GoogleIcon(props) {
  return (
    <svg viewBox="0 0 48 48" {...props}>
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}

export function AppleIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M17.05 12.94c-.02-2.36 1.93-3.49 2.02-3.55-1.1-1.61-2.81-1.83-3.42-1.86-1.46-.15-2.85.86-3.59.86-.74 0-1.88-.84-3.09-.82-1.59.02-3.06.92-3.88 2.34-1.65 2.87-.42 7.12 1.19 9.44.79 1.14 1.73 2.42 2.96 2.37 1.19-.05 1.64-.77 3.08-.77 1.44 0 1.84.77 3.09.75 1.28-.02 2.09-1.16 2.87-2.31.9-1.32 1.27-2.6 1.29-2.67-.03-.01-2.48-.95-2.5-3.78zM14.67 5.6c.65-.79 1.09-1.89.97-2.98-.94.04-2.07.62-2.74 1.41-.6.7-1.13 1.82-.99 2.89 1.05.08 2.11-.53 2.76-1.32z" />
    </svg>
  )
}

/* --- Landing page --- */
export const ForumIcon = (p) => (
  <Stroke width={1.9} {...p}><path d="M21 12a8 8 0 0 1-11.5 7.2L4 20l1.1-5A8 8 0 1 1 21 12Z" /></Stroke>
)
export const NewsIcon = (p) => (
  <Stroke width={1.9} {...p}>
    <rect x="3" y="4" width="14" height="16" rx="1.5" />
    <path d="M17 8h4v10a2 2 0 0 1-2 2h-2M7 8h6M7 12h6M7 16h4" />
  </Stroke>
)
export const MailIcon = (p) => (
  <Stroke width={1.9} {...p}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></Stroke>
)
export const DataRoomIcon = (p) => (
  <Stroke width={1.9} {...p}>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />
    <path d="M12 12v4M10 14h4" />
  </Stroke>
)
export const AnalyticsIcon = (p) => (
  <Stroke width={1.9} {...p}><path d="M4 20V10M12 20V4M20 20v-7" /></Stroke>
)
export const BoltIcon = (p) => (
  <Stroke width={1.9} {...p}><path d="M13 3 4 14h7l-1 7 9-11h-7l1-7z" /></Stroke>
)
export const ClockIcon = (p) => (
  <Stroke width={1.9} {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.2 2" /></Stroke>
)
export const StackIcon = (p) => (
  <Stroke width={1.9} {...p}><rect x="4" y="4" width="16" height="16" rx="3" /><path d="M9 12h6M12 9v6" /></Stroke>
)
