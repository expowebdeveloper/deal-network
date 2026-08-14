import Modal, { ModalHead, ModalTitle, ModalBody } from '../ui/Modal'
import { CloseIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import { landingColumns } from '../../data/onboarding'

/** Preview of the signed-out marketing page. */
export default function LandingModal() {
  const { closeModal, closeFlow } = useApp()

  // A preview of the signed-out marketing page — dismiss it back to the app.
  function getStarted() {
    closeModal()
    closeFlow()
  }

  return (
    <Modal width="wide">
      <ModalHead>
        <ModalTitle title="Landing page" sub="What someone sees before they have an account." />
        <button className="pr-close pr-close-dark" onClick={closeModal}>
          <CloseIcon />
        </button>
      </ModalHead>

      <ModalBody className="modal-body-flush">
        <div className="landing-hero">
          <div className="landing-eyebrow">FOR DEVELOPERS, INVESTORS, BROKERS &amp; LENDERS</div>
          <h1>Where property people actually find each other.</h1>
          <p>
            Profiles, communities and contact management built around the markets and asset classes
            you really work in.
          </p>
          <button className="btn btn-lg landing-cta" onClick={getStarted}>
            Get started 
          </button>
        </div>

        <div className="landing-cols">
          {landingColumns.map((c) => (
            <div className="landing-col" key={c.t}>
              <div className="t">{c.t}</div>
              <div className="d">{c.d}</div>
            </div>
          ))}
        </div>
      </ModalBody>
    </Modal>
  )
}
