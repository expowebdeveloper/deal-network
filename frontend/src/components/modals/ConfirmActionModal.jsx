import { useState } from 'react'
import Modal, { ModalBody, ModalFoot, ModalHead, ModalTitle } from '../ui/Modal'
import { useApp } from '../../context/AppContext'

/**
 * "Are you sure?" for an action that is awkward to undo.
 *
 * The work itself stays with the caller: `onConfirm` is awaited, and anything it
 * throws is shown here rather than closing over a failure. Only a clean return
 * dismisses the sheet.
 *
 * `onCancel` exists because the app renders one modal at a time — a confirm
 * opened from inside another modal replaces it, so the caller passes a way to
 * put back whatever the member was looking at.
 */
export default function ConfirmActionModal({
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'default',
  onConfirm,
  onCancel,
}) {
  const { closeModal } = useApp()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      await onConfirm?.()
      closeModal()
    } catch (err) {
      // Staying open with the reason beats closing and leaving them to guess
      // why nothing happened — leaving a community you own is refused, for one.
      setError(err?.message || 'That did not work. Please try again.')
      setBusy(false)
    }
  }

  function cancel() {
    if (busy) return
    if (onCancel) onCancel()
    else closeModal()
  }

  return (
    <Modal width="narrow">
      <ModalHead>
        <ModalTitle title={title} />
      </ModalHead>
      <ModalBody>
        <p className="confirm-message">{message}</p>
        {error && <div className="inline-error" style={{ marginTop: 12 }}>{error}</div>}
      </ModalBody>
      <ModalFoot>
        <button className="btn btn-ghost" onClick={cancel} disabled={busy}>
          {cancelLabel}
        </button>
        <button
          className={`btn ${tone === 'danger' ? 'btn-danger' : 'btn-primary'}`}
          onClick={confirm}
          data-busy={busy}
          disabled={busy}
        >
          {confirmLabel}
        </button>
      </ModalFoot>
    </Modal>
  )
}
