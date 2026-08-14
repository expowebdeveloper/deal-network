import { useState } from 'react'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import Field, { FieldRow } from '../ui/Field'
import { useApp } from '../../context/AppContext'
import { createContact, isContactLimitReached } from '../../lib/contacts'
import { STAGES } from '../../data/contacts'

const ROLES = ['Developer', 'Investor', 'Broker', 'Lender', 'Service provider']

const blank = (value) => (value.trim() ? value.trim() : null)

/**
 * Add a contact to your own relationship record.
 *
 * The free plan allows 25; the API refuses the 26th with `contact_limit_reached`,
 * which is shown here as an upgrade prompt rather than a raw error.
 */
export default function AddContactModal({ onAdded }) {
  const { closeModal } = useApp()

  const [form, setForm] = useState({
    name: '', company: '', role: '', market: '', email: '', phone: '',
    stage: STAGES[0], source: '', notes: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [limitHit, setLimitHit] = useState(false)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function save() {
    if (saving) return
    if (!form.name.trim()) {
      setError('Give the contact a name.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const created = await createContact({
        name: form.name.trim(),
        company: blank(form.company),
        role: form.role || null,
        market: blank(form.market),
        // The board shows a short market tag; fall back to the city.
        market_short: blank(form.market)?.split(',')[0] ?? null,
        email: blank(form.email),
        phone: blank(form.phone),
        stage: form.stage,
        source: blank(form.source),
        notes: blank(form.notes),
      })
      onAdded?.(created)
      closeModal()
    } catch (err) {
      if (isContactLimitReached(err)) setLimitHit(true)
      else setError(err.message)
      setSaving(false)
    }
  }

  return (
    <Modal>
      <ModalHead>
        <ModalTitle
          title="Add a contact"
          sub="Only you can see this. It is your record, not a network profile."
        />
      </ModalHead>

      <ModalBody>
        {limitHit ? (
          <div className="inline-error">
            You have reached the 25 contacts included with Early access. Move to Member
            for unlimited contacts.
          </div>
        ) : error ? (
          <div className="inline-error">{error}</div>
        ) : null}

        <Field label="Name">
          <input value={form.name} onChange={set('name')} placeholder="Who they are" autoFocus />
        </Field>

        <FieldRow>
          <Field label="Company">
            <input value={form.company} onChange={set('company')} />
          </Field>
          <Field label="Role">
            <select value={form.role} onChange={set('role')}>
              <option value="">Not set</option>
              {ROLES.map((r) => <option key={r}>{r}</option>)}
            </select>
          </Field>
        </FieldRow>

        <FieldRow>
          <Field label="Market">
            <input value={form.market} onChange={set('market')} placeholder="e.g. Mohali, IN" />
          </Field>
          <Field label="Stage">
            <select value={form.stage} onChange={set('stage')}>
              {STAGES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
        </FieldRow>

        <FieldRow>
          <Field label="Email">
            <input type="email" value={form.email} onChange={set('email')} />
          </Field>
          <Field label="Phone">
            <input value={form.phone} onChange={set('phone')} />
          </Field>
        </FieldRow>

        <Field label="Where you met" hint="Shown in the Source column.">
          <input value={form.source} onChange={set('source')} placeholder="e.g. Bangalore Developers" />
        </Field>

        <Field label="Notes" className="last-field">
          <textarea value={form.notes} onChange={set('notes')}
                    placeholder="Anything worth remembering before the next conversation." />
        </Field>
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal} disabled={saving}>Cancel</button>
        <button className="btn btn-primary" onClick={save} data-busy={saving} disabled={saving}>
          {saving ? 'Adding…' : 'Add contact'}
        </button>
      </ModalFoot>
    </Modal>
  )
}
