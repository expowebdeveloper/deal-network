import { useState } from 'react'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import Avatar from '../ui/Avatar'
import { useApp } from '../../context/AppContext'
import { roleOptions } from '../../data/onboarding'

export default function RoleModal() {
  const { closeModal, openModal } = useApp()
  const [picked, setPicked] = useState(null)

  return (
    <Modal>
      <ModalHead>
        <ModalTitle
          title="What describes you best?"
          sub="This sets which communities and members we suggest first. You can change it later."
        />
      </ModalHead>

      <ModalBody>
        {roleOptions.map((r, i) => (
          <button
            key={r.title}
            className={`card role-opt${picked === r.title ? ' on' : ''}`}
            onClick={() => setPicked(r.title)}
          >
            <Avatar initials={i + 1} color={`a${i + 1}`} size="sm" />
            <div style={{ flex: 1 }}>
              <div className="t">{r.title}</div>
              <div className="d">{r.desc}</div>
            </div>
            <div className="radio" />
          </button>
        ))}
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal}>Back</button>
        <button className="btn btn-primary" onClick={() => openModal('wizard')}>Continue</button>
      </ModalFoot>
    </Modal>
  )
}
