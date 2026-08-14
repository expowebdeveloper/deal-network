import { useNavigate } from 'react-router-dom'
import Modal, { ModalBody, ModalFoot } from '../ui/Modal'
import { CheckIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'

/** Shared success sheet used after sending a request and after checkout. */
function Confirm({ title, message, children }) {
  return (
    <Modal width="narrow">
      <ModalBody className="confirm-body">
        <div className="confirm-icon"><CheckIcon /></div>
        <h2>{title}</h2>
        <p>{message}</p>
      </ModalBody>
      <ModalFoot center>{children}</ModalFoot>
    </Modal>
  )
}

export function ConnectSentModal({ name }) {
  const { closeModal } = useApp()
  const navigate = useNavigate()

  return (
    <Confirm
      title="Request sent"
      message={`${name} has been added to your contacts as a new lead. You will be notified when they respond.`}
    >
      <button className="btn btn-ghost" onClick={closeModal}>Close</button>
      <button
        className="btn btn-primary"
        onClick={() => { closeModal(); navigate('/contacts') }}
      >
        Open contacts
      </button>
    </Confirm>
  )
}

export function PaidModal({ plan }) {
  const { closeModal } = useApp()

  return (
    <Confirm
      title={`You are on ${plan}`}
      message="Nothing is charged while early access is running. We will email you before the first payment is taken."
    >
      <button className="btn btn-primary" onClick={closeModal}>Done</button>
    </Confirm>
  )
}
