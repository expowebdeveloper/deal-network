import { useNavigate } from 'react-router-dom'
import Modal, { ModalHead, ModalBody, ModalFoot } from '../ui/Modal'
import { useApp } from '../../context/AppContext'
import { ICONS } from '../landing/moduleIcons'
import { CheckIcon, CloseIcon } from '../icons/Icons'
import { modules } from '../../data/landing'

/** What a module on the landing page actually includes. */
export default function FeatureModal({ moduleId }) {
  const { closeModal, openModal } = useApp()
  const navigate = useNavigate()

  const module = modules.find((m) => m.id === moduleId)
  if (!module) return null

  const Icon = ICONS[module.icon]

  return (
    <Modal className="feature-modal">
      <ModalHead>
        <div className={`feat-avatar ${module.avatar}`}><Icon /></div>
        <div className="tt">
          <h2>{module.title}</h2>
          {module.pro && <span className="tag tag-gold">Pro feature</span>}
          <span className="chip">{module.phase}</span>
        </div>
        <button className="modal-close" onClick={closeModal} aria-label="Close">
          <CloseIcon />
        </button>
      </ModalHead>

      <ModalBody>
        <p>{module.detail.summary}</p>
        <div className="sec-title">What&apos;s included</div>
        <ul>
          {module.detail.bullets.map((bullet) => (
            <li key={bullet}><CheckIcon /><span>{bullet}</span></li>
          ))}
        </ul>
        <div className="feature-status">{module.detail.status}</div>
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal}>Close</button>
        <button
          className="btn btn-primary"
          onClick={() => {
            navigate('/login')
            openModal('login', { onClose: () => navigate('/', { replace: true }) })
          }}
        >
          Get started
        </button>
      </ModalFoot>
    </Modal>
  )
}
