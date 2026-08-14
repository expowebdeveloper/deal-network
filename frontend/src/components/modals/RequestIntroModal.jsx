import { useEffect, useState } from 'react'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import Field from '../ui/Field'
import { useApp } from '../../context/AppContext'
import { requestIntroduction, listMembers } from '../../lib/investors'
import { isUpgradeRequired } from '../../lib/contacts'

/**
 * Ask to be introduced to another member.
 *
 * A Member feature: the API answers `upgrade_required` for Early access, which
 * is shown here as an upgrade prompt rather than a raw error.
 */
export default function RequestIntroModal({ onSent }) {
  const { closeModal } = useApp()

  const [people, setPeople] = useState([])
  const [toUserId, setToUserId] = useState('')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [locked, setLocked] = useState(false)

  useEffect(() => {
    let cancelled = false
    listMembers({ limit: 50 })
      .then((page) => {
        if (cancelled) return
        setPeople(page.items)
        setToUserId((cur) => cur || page.items[0]?.id || '')
      })
      .catch((err) => !cancelled && setError(err.message))
    return () => { cancelled = true }
  }, [])

  async function send() {
    if (sending || !toUserId) return
    setSending(true)
    setError(null)
    try {
      const created = await requestIntroduction({
        toUserId,
        message: message.trim() || null,
      })
      onSent?.(created)
      closeModal()
    } catch (err) {
      if (isUpgradeRequired(err)) setLocked(true)
      else setError(err.message)
      setSending(false)
    }
  }

  return (
    <Modal>
      <ModalHead>
        <ModalTitle
          title="Request an introduction"
          sub="They get an email with your note, and can accept or decline."
        />
      </ModalHead>

      <ModalBody>
        {locked ? (
          <div className="inline-error">
            Introduction requests are a Member feature. Move to Member to ask for warm
            introductions across the network.
          </div>
        ) : error ? (
          <div className="inline-error">{error}</div>
        ) : null}

        <Field label="Who would you like to meet">
          <select value={toUserId} onChange={(e) => setToUserId(e.target.value)}>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {[p.name, p.company, p.location].filter(Boolean).join(' · ')}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label="Your note"
          hint="Why you want the introduction — a line or two is plenty."
          className="last-field"
        >
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="We are both in the Mohali market and I would value a conversation about…"
          />
        </Field>
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal} disabled={sending}>Cancel</button>
        <button
          className="btn btn-primary"
          onClick={send}
          data-busy={sending}
          disabled={sending || !toUserId}
        >
          {sending ? 'Sending…' : 'Send request'}
        </button>
      </ModalFoot>
    </Modal>
  )
}
