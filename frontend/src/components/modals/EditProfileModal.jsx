import { useState } from 'react'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import Field, { FieldRow } from '../ui/Field'
import { useApp } from '../../context/AppContext'
import { updateMe, updateMandate } from '../../lib/user'

const ROLES = ['Developer', 'Investor', 'Broker', 'Lender', 'Service provider']

/** Blank in the form means "not set", which the API stores as null. */
const clean = (value) => (value.trim() ? value.trim() : null)

/**
 * Edit profile.
 *
 * Saves in two calls because the profile is two records: the member
 * (PATCH /api/me) and what they tell investors (PUT /api/me/mandate). Only the
 * fields that actually changed are sent, so nothing is overwritten by accident.
 */
export default function EditProfileModal({ user, mandate, onSaved }) {
  const { closeModal, loadSession } = useApp()

  const [form, setForm] = useState({
    name: user?.name ?? '',
    role: user?.role ?? '',
    title: user?.title ?? '',
    company: user?.company ?? '',
    location: user?.location ?? '',
    focus: user?.focus ?? '',
    bio: user?.bio ?? '',
    completed_projects: String(user?.completed_projects ?? 0),
    units_delivered: String(user?.units_delivered ?? 0),
    active_projects: String(user?.active_projects ?? 0),
    markets: mandate?.markets ?? '',
    typical_raise: mandate?.typical_raise ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function save() {
    if (saving) return
    if (!form.name.trim()) {
      setError('Your name cannot be blank.')
      return
    }
    setSaving(true)
    setError(null)

    const changes = {}
    const put = (key, value) => {
      const before = user?.[key] ?? null
      if (value !== before) changes[key] = value
    }
    put('name', form.name.trim())
    put('role', form.role || null)
    put('title', clean(form.title))
    put('company', clean(form.company))
    put('location', clean(form.location))
    put('focus', clean(form.focus))
    put('bio', clean(form.bio))
    for (const key of ['completed_projects', 'units_delivered', 'active_projects']) {
      const n = Math.max(0, parseInt(form[key], 10) || 0)
      if (n !== (user?.[key] ?? 0)) changes[key] = n
    }

    const mandateChanges = {}
    for (const key of ['markets', 'typical_raise']) {
      const value = clean(form[key])
      if (value !== (mandate?.[key] ?? null)) mandateChanges[key] = value
    }

    try {
      if (Object.keys(changes).length) await updateMe(changes)
      const savedMandate = Object.keys(mandateChanges).length
        ? await updateMandate(mandateChanges)
        : mandate
      // Refresh the session so the topbar, sidebar and profile all agree.
      await loadSession()
      onSaved?.(savedMandate)
      closeModal()
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <Modal>
      <ModalHead>
        <ModalTitle
          title="Edit profile"
          sub="This is what other members see. Leave a field blank to keep it off your profile."
        />
      </ModalHead>

      <ModalBody>
        {error && <div className="inline-error">{error}</div>}

        <Field label="Name">
          <input value={form.name} onChange={set('name')} autoFocus />
        </Field>

        <FieldRow>
          <Field label="Role">
            <select value={form.role} onChange={set('role')}>
              <option value="">Not set</option>
              {ROLES.map((r) => <option key={r}>{r}</option>)}
            </select>
          </Field>
          <Field label="Job title">
            <input value={form.title} onChange={set('title')} placeholder="e.g. Managing Partner" />
          </Field>
        </FieldRow>

        <FieldRow>
          <Field label="Company">
            <input value={form.company} onChange={set('company')} />
          </Field>
          <Field label="Location">
            <input value={form.location} onChange={set('location')} placeholder="e.g. Mohali, IN" />
          </Field>
        </FieldRow>

        <Field label="Asset classes" hint="Shown next to your location.">
          <input value={form.focus} onChange={set('focus')} placeholder="e.g. Residential, Mixed-use" />
        </Field>

        <FieldRow>
          <Field label="Markets" hint="Where you work, for investors.">
            <input value={form.markets} onChange={set('markets')} placeholder="e.g. Mohali, Chandigarh" />
          </Field>
          <Field label="Typical raise size">
            <input value={form.typical_raise} onChange={set('typical_raise')} placeholder="e.g. ₹8–25 Cr" />
          </Field>
        </FieldRow>

        <FieldRow cols={3}>
          <Field label="Completed projects">
            <input type="number" min="0" value={form.completed_projects}
                   onChange={set('completed_projects')} />
          </Field>
          <Field label="Units delivered">
            <input type="number" min="0" value={form.units_delivered}
                   onChange={set('units_delivered')} />
          </Field>
          <Field label="Active projects">
            <input type="number" min="0" value={form.active_projects}
                   onChange={set('active_projects')} />
          </Field>
        </FieldRow>

        <Field label="About you" className="last-field">
          <textarea value={form.bio} onChange={set('bio')}
                    placeholder="One or two lines other members will see on your profile." />
        </Field>
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal} disabled={saving}>Cancel</button>
        <button className="btn btn-primary" onClick={save} data-busy={saving} disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </ModalFoot>
    </Modal>
  )
}
