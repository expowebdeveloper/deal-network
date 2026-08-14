import {
  HomeIcon, CommunitiesIcon, SearchIcon, InvestorsIcon,
  ContactsIcon, PlansIcon, LockIcon, UnderwritingIcon, ProfileIcon,
} from '../components/icons/Icons'

/** Sidebar groups. `soon` items are rendered locked and are not links. */
export const sidebarGroups = [
  {
    items: [
      { to: '/', label: 'Home', Icon: HomeIcon, end: true },
      // `countKey` is filled in live by the Sidebar; no hardcoded numbers.
      { to: '/communities', label: 'Communities', Icon: CommunitiesIcon, countKey: 'communities' },
      { to: '/members', label: 'Members', Icon: SearchIcon },
    ],
  },
  {
    label: 'Business',
    items: [
      { to: '/investors', label: 'Investors', Icon: InvestorsIcon },
      { to: '/contacts', label: 'Contacts', Icon: ContactsIcon, countKey: 'contacts' },
      { to: '/plans', label: 'Plans', Icon: PlansIcon },
    ],
  },
  {
    label: 'Coming soon',
    items: [
      { label: 'Data Room', Icon: LockIcon, soon: true },
      { label: 'Underwriting', Icon: UnderwritingIcon, soon: true },
    ],
  },
]

/** Phone bottom bar — five slots, shorter labels. */
export const bottomNavItems = [
  { to: '/', label: 'Home', Icon: HomeIcon, end: true },
  { to: '/communities', label: 'Groups', Icon: CommunitiesIcon },
  { to: '/members', label: 'Members', Icon: SearchIcon },
  { to: '/contacts', label: 'Contacts', Icon: ContactsIcon },
  { to: '/profile', label: 'You', Icon: ProfileIcon },
]
