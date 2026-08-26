import { useState } from 'react'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import { useApp } from '../../context/AppContext'
import { LockIcon, InfoIcon } from '../icons/Icons'
import {
  startCheckout, goToStripe, isBillingUnconfigured, billingErrorMessage,
} from '../../lib/billing'

/**
 * The confirm-and-pay step for a paid plan.
 *
 * There is deliberately **no card form here.** This screen shows what is about
 * to be charged and then hands the browser to Stripe's hosted Checkout page,
 * where the card is entered on Stripe's domain. An earlier version of this file
 * collected the card number into our own form and posted it to our API — that
 * put the whole backend in PCI-DSS scope, and it is why nothing on this page
 * has an input any more.
 *
 * `plan` is the tier code (`member`, `professional`); `price` and `name` are for
 * display and come from the server's price list.
 */
export default function CheckoutModal({ plan, name, price, interval = '/month' }) {
  const { closeModal } = useApp()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function pay() {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const { checkout_url } = await startCheckout(plan)
      // Full page navigation, not a fetch: Checkout is Stripe's page, and the
      // modal is left behind with the document.
      goToStripe(checkout_url)
    } catch (err) {
      setError(
        isBillingUnconfigured(err)
          ? 'Card payments are not switched on for this environment yet. '
            + 'Nothing has been charged — early access stays free in the meantime.'
          : billingErrorMessage(err, 'Could not open the payment page.'),
      )
      setBusy(false)
    }
  }

  return (
    <Modal>
      <ModalHead>
        <ModalTitle
          title={`Subscribe to ${name || plan}`}
          sub="You will be taken to Stripe to enter your card. We never see your card details."
        />
      </ModalHead>

      <ModalBody>
        <div className="card co-summary">
          <div className="co-summary-row">
            <div>
              <div className="co-plan">{name || plan} plan</div>
              <div className="co-cycle">Monthly · cancel anytime</div>
            </div>
            <div className="co-price">
              ${price}<span>{interval}</span>
            </div>
          </div>
        </div>

        <ul className="co-points">
          <li>
            <LockIcon />
            <span>
              Your card is entered on Stripe’s secure page, not on Deal Network.
              We only ever store the last four digits.
            </span>
          </li>
          <li>
            <InfoIcon />
            <span>
              Your plan switches on the moment the payment clears. If you cancel
              on Stripe’s page nothing is charged and nothing changes.
            </span>
          </li>
        </ul>

        {error && <div className="inline-error">{error}</div>}
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal} disabled={busy}>
          Cancel
        </button>
        <button className="btn btn-primary" onClick={pay} data-busy={busy} disabled={busy}>
          {busy ? 'Opening Stripe…' : `Continue to payment`}
        </button>
      </ModalFoot>
    </Modal>
  )
}
