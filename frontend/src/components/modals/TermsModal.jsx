import { useState } from 'react'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import { useApp } from '../../context/AppContext'
import { termsCopy, termsChecks } from '../../data/onboarding'

/** Renders the mixed plain/bold/muted runs used in the consent labels. */
function Label({ parts }) {
  return parts.map((part, i) => {
    if (typeof part === 'string') return <span key={i}>{part}</span>
    if (part.b) return <b key={i}>{part.b}</b>
    return <span key={i} style={{ color: 'var(--muted)' }}>{part.muted}</span>
  })
}

/** `onBack` lets whoever opened this put their own modal back — there is only
    one modal slot, so Back would otherwise drop the caller's dialog. */
export default function TermsModal({ onBack }) {
  const { closeModal, openModal } = useApp()
  const [checked, setChecked] = useState({})

  return (
    <Modal>
      <ModalHead>
        <ModalTitle
          title="Before you continue"
          sub="Plain-language summary of what you are agreeing to."
        />
      </ModalHead>

      <ModalBody>
        <div className="card terms-box">
          <div className="terms-text">
            {termsCopy.map((c, i) => (
              <span key={c.h}>
                <b>{c.h}</b> {c.p}
                {i < termsCopy.length - 1 && <><br /><br /></>}
              </span>
            ))}
          </div>
        </div>

        {termsChecks.map((c) => (
          <label className="terms-check" key={c.id}>
            <input
              type="checkbox"
              checked={!!checked[c.id]}
              onChange={(e) => setChecked((v) => ({ ...v, [c.id]: e.target.checked }))}
            />
            <span><Label parts={c.text} /></span>
          </label>
        ))}
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={onBack || closeModal}>Back</button>
        <button className="btn btn-primary" onClick={() => openModal('role')}>Continue</button>
      </ModalFoot>
    </Modal>
  )
}
