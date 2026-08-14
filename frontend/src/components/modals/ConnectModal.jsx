import { useState } from 'react'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import Avatar from '../ui/Avatar'
import Field from '../ui/Field'
import { GlobeIcon } from '../icons/Icons'
import { useApp } from '../../context/AppContext'
import { api } from '../../lib/api'

/** Two locations count as different markets when their country differs. */
function isCrossMarket(theirs, mine) {
  if (!theirs || !mine) return false
  return theirs.split(',')[1] !== mine.split(',')[1]
}

export default function ConnectModal({ person, onSent }) {
  const { closeModal, openModal, user } = useApp()
  const mine = user?.location
  const cross = isCrossMarket(person.location, mine)

  const [note, setNote] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)

  async function send() {
    if (!person.id) {
      setError('This member cannot be connected to yet.')
      return
    }
    setSending(true)
    setError(null)
    try {
      await api.post('/api/connections', {
        addressee_id: person.id,
        note: note.trim() || null,
      })
      onSent?.()
      openModal('connect-sent', { name: person.name })
    } catch (err) {
      setError(err.message)
      setSending(false)
    }
  }

  return (
    <Modal>
      <ModalHead>
        <Avatar initials={person.initials} color={person.color} size="lg" />
        <ModalTitle
          title={`Connect with ${person.name}`}
          sub={`${person.role} · ${person.company} · ${person.location}`}
        />
      </ModalHead>

      <ModalBody>
        {error && <div className="inline-error">{error}</div>}

        {cross && (
          <div className="earlybar" style={{ marginBottom: 18, padding: '13px 15px' }}>
            <GlobeIcon />
            <div>
              <h4>Connecting across markets</h4>
              <p>
                You are in <b>{mine}</b> and they are in <b>{person.location}</b>. Markets do not
                restrict who you can reach — requests work the same way anywhere on the network.
              </p>
            </div>
          </div>
        )}

        <Field
          label="Add a note (optional)"
          hint="Requests with a note are accepted far more often."
        >
          <textarea
            placeholder="How you know them, or why you are reaching out."
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </Field>

        <div className="card connect-note">
          <div className="sec-title" style={{ marginBottom: 9 }}>What connecting does</div>
          <div className="connect-note-body">
            • They appear in your contacts as a new lead<br />
            • You both see member-level profile fields<br />
            • Neither side sees private financials, lenders or investor names
          </div>
        </div>
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal} disabled={sending}>
          Cancel
        </button>
        <button className="btn btn-primary" onClick={send} data-busy={sending}>
          {sending ? 'Sending…' : 'Send request'}
        </button>
      </ModalFoot>
    </Modal>
  )
}
