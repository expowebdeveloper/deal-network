import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import Field, { FieldRow } from '../ui/Field'
import { useApp } from '../../context/AppContext'

export default function CheckoutModal({ plan, price }) {
  const { closeModal, openModal } = useApp()

  return (
    <Modal>
      <ModalHead>
        <ModalTitle
          title={`Subscribe to ${plan}`}
          sub="Your card is not charged until early access ends."
        />
      </ModalHead>

      <ModalBody>
        <div className="card co-summary">
          <div className="co-summary-row">
            <div>
              <div className="co-plan">{plan} plan</div>
              <div className="co-cycle">Monthly · cancel anytime</div>
            </div>
            <div className="co-price">${price}<span>/mo</span></div>
          </div>
        </div>

        <Field label="Card number">
          <input placeholder="1234 1234 1234 1234" />
        </Field>
        <FieldRow>
          <Field label="Expiry"><input placeholder="MM / YY" /></Field>
          <Field label="CVC"><input placeholder="123" /></Field>
        </FieldRow>
        <Field label="Name on card">
          <input placeholder="Vikram Sethi" />
        </Field>
        <Field label="Billing country" className="last-field">
          <select defaultValue="India">
            <option>India</option>
            <option>United States</option>
            <option>United Kingdom</option>
          </select>
        </Field>
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal}>Cancel</button>
        <button className="btn btn-primary" onClick={() => openModal('paid', { plan })}>
          Start subscription
        </button>
      </ModalFoot>
    </Modal>
  )
}
