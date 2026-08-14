import { useApp } from '../../context/AppContext'
import CommunityModal from './CommunityModal'
import CreateCommunityModal from './CreateCommunityModal'
import ConnectModal from './ConnectModal'
import CheckoutModal from './CheckoutModal'
import EditProfileModal from './EditProfileModal'
import AddContactModal from './AddContactModal'
import RequestIntroModal from './RequestIntroModal'
import PhaseModal from './PhaseModal'
import LoginModal from './LoginModal'
import LandingModal from './LandingModal'
import TermsModal from './TermsModal'
import RoleModal from './RoleModal'
import WizardModal from './WizardModal'
import { ConnectSentModal, PaidModal } from './ConfirmModal'

/** One modal at a time, keyed by the name passed to openModal(). */
const MODALS = {
  community: CommunityModal,
  'create-community': CreateCommunityModal,
  connect: ConnectModal,
  'connect-sent': ConnectSentModal,
  checkout: CheckoutModal,
  'edit-profile': EditProfileModal,
  'add-contact': AddContactModal,
  'request-intro': RequestIntroModal,
  phase: PhaseModal,
  login: LoginModal,
  paid: PaidModal,
  landing: LandingModal,
  terms: TermsModal,
  role: RoleModal,
  wizard: WizardModal,
}

export default function ModalHost() {
  const { modal } = useApp()
  if (!modal) return null

  const Component = MODALS[modal.name]
  if (!Component) return null

  return <Component {...modal.props} />
}
