import { useNavigate } from 'react-router-dom'
import Modal, { ModalHead, ModalBody, ModalFoot } from '../ui/Modal'
import { useApp } from '../../context/AppContext'
import { ICONS } from '../landing/moduleIcons'
import { CloseIcon } from '../icons/Icons'
import { phases, phaseItemCount } from '../../data/phases'

/** Everything a phase contains — every feature group, item and note.
 *
 *  Delivery status is deliberately not shown: `status` is still on each item in
 *  data/phases.js, straight from card.txt, but this is a page prospects read and
 *  a per-item build tracker is not what it is for. */
export default function PhaseModal({ phaseNumber }) {
  const { closeModal, openModal } = useApp()
  const navigate = useNavigate()

  const phase = phases.find((p) => p.n === phaseNumber)
  if (!phase) return null

  const Icon = ICONS[phase.icon]

  return (
    <Modal width="wide" className="feature-modal phase-modal">
      <ModalHead>
        <div className={`feat-avatar ${phase.avatar}`}><Icon /></div>
        <div className="tt">
          <h2>{phase.name}</h2>
          <span className="chip">Phase {phase.n}</span>
          <span className="tag">{phaseItemCount(phase)} features</span>
        </div>
        <button className="modal-close" onClick={closeModal} aria-label="Close">
          <CloseIcon />
        </button>
      </ModalHead>

      <ModalBody>
        <p>{phase.blurb}</p>

        {phase.groups.map((group) => (
          <div className="phase-group" key={group.code}>
            <div className="sec-title">
              <span className="phase-code">{group.code}</span>
              {group.name}
            </div>
            <ul>
              {group.items.map((item) => (
                <li key={item.code}>
                  <span className="phase-bullet" />
                  <span className="phase-item">
                    {item.label}
                    {item.notes && <span className="phase-note">{item.notes}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
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
