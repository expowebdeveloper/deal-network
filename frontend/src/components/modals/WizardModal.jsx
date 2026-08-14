import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import Field, { FieldRow } from '../ui/Field'
import Chip from '../ui/Chip'
import { useApp } from '../../context/AppContext'
import { assetClassChips } from '../../data/onboarding'

const TOTAL_STEPS = 4
const CURRENT_STEP = 2

export default function WizardModal() {
  const { closeModal, closeFlow } = useApp()
  const navigate = useNavigate()
  const [selected, setSelected] = useState(
    () => new Set(assetClassChips.filter((c) => c.on).map((c) => c.label)),
  )

  function toggle(label) {
    setSelected((cur) => {
      const next = new Set(cur)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }

  function finish() {
    closeModal()
    closeFlow()
    navigate('/')
  }

  return (
    <Modal>
      <ModalHead>
        <ModalTitle title="Set up your profile" sub={`Step ${CURRENT_STEP} of ${TOTAL_STEPS} · Company details`}>
          <div className="steps">
            {Array.from({ length: TOTAL_STEPS }, (_, i) => (
              <div key={i} className={`step${i < CURRENT_STEP ? ' on' : ''}`} />
            ))}
          </div>
        </ModalTitle>
      </ModalHead>

      <ModalBody>
        <Field label="Company name">
          <input defaultValue="Meridian Developments" />
        </Field>

        <FieldRow>
          <Field label="Primary market">
            <select defaultValue="Mohali, IN">
              <option>Mohali, IN</option>
              <option>Bangalore, IN</option>
              <option>New York, US</option>
            </select>
          </Field>
          <Field label="Team size">
            <select defaultValue="Just me">
              <option>Just me</option>
              <option>2–10</option>
              <option>11–50</option>
              <option>50+</option>
            </select>
          </Field>
        </FieldRow>

        <Field label="Asset classes you work in">
          <div className="chip-wrap">
            {assetClassChips.map((c) => (
              <Chip key={c.label} on={selected.has(c.label)} onClick={() => toggle(c.label)}>
                {c.label}
              </Chip>
            ))}
          </div>
        </Field>

        <Field label="Short description" className="last-field">
          <textarea placeholder="One or two lines other members will see on your profile." />
        </Field>
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal}>Back</button>
        <button className="btn btn-primary" onClick={finish}>Finish setup</button>
      </ModalFoot>
    </Modal>
  )
}
