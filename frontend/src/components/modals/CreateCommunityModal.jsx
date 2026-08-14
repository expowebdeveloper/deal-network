import { useState } from 'react'
import Modal, { ModalHead, ModalTitle, ModalBody, ModalFoot } from '../ui/Modal'
import Field from '../ui/Field'
import { useApp } from '../../context/AppContext'
import { createCommunity } from '../../lib/communities'

const REGIONS = ['Mohali, IN', 'Bangalore, IN', 'New York, US', 'Bay Area, US']
const ASSET_CLASSES = ['Residential', 'Mixed-use', 'Medical', 'Industrial', 'Retail', 'Hospitality']
const BANNERS = ['b1', 'b2', 'b3', 'b4', 'b5', 'b6']

const JOIN_POLICIES = [
  { value: 'open', label: 'Open — any member can join' },
  { value: 'request', label: 'Request to join — you approve' },
  { value: 'invite', label: 'Invite only' },
]

export default function CreateCommunityModal({ onCreated }) {
  const { closeModal } = useApp()

  const [form, setForm] = useState({
    name: '',
    kind: 'region',
    region: REGIONS[0],
    assetClass: ASSET_CLASSES[0],
    joinPolicy: 'open',
    description: '',
    banner: 'b1',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function submit() {
    if (!form.name.trim()) {
      setError('Give the community a name.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await createCommunity({
        name: form.name.trim(),
        kind: form.kind,
        // A market community is pinned to a city; an asset-class one spans markets.
        location: form.kind === 'region' ? form.region : 'Global',
        description: form.description.trim() || null,
        banner: form.banner,
        join_policy: form.joinPolicy,
        channels: ['# general', '# introductions'],
      })
      onCreated?.()
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
          title="Create a community"
          sub="Communities are organised either by the market you work in or the asset class you specialise in."
        />
      </ModalHead>

      <ModalBody>
        {error && <div className="inline-error">{error}</div>}

        <Field label="Community name">
          <input
            placeholder="e.g. Pune Residential Developers"
            value={form.name}
            onChange={set('name')}
            autoFocus
          />
        </Field>

        <Field
          label="Organised by"
          hint="This decides how the community is listed and who gets suggested it."
        >
          <select value={form.kind} onChange={set('kind')}>
            <option value="region">Market / region</option>
            <option value="industry">Asset class</option>
          </select>
        </Field>

        {/* Only one of these applies. An asset-class community is defined by its
            name, so there is no separate asset-class field to store. */}
        {form.kind === 'region' ? (
          <Field label="Market" hint="Where this community operates.">
            <select value={form.region} onChange={set('region')}>
              {REGIONS.map((r) => <option key={r}>{r}</option>)}
            </select>
          </Field>
        ) : (
          <Field
            label="Asset class"
            hint="Pick one to name the community after, or type your own name above."
          >
            <select
              value={form.assetClass}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  assetClass: e.target.value,
                  // Only overwrite a name the user has not typed themselves.
                  name: f.name && f.name !== f.assetClass ? f.name : e.target.value,
                }))
              }
            >
              {ASSET_CLASSES.map((a) => <option key={a}>{a}</option>)}
            </select>
          </Field>
        )}

        <Field label="Who can join">
          <select value={form.joinPolicy} onChange={set('joinPolicy')}>
            {JOIN_POLICIES.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Banner">
          <div className="banner-picker">
            {BANNERS.map((b) => (
              <button
                key={b}
                type="button"
                className={`banner-swatch ${b}${form.banner === b ? ' on' : ''}`}
                aria-label={`Banner ${b}`}
                onClick={() => setForm((f) => ({ ...f, banner: b }))}
              />
            ))}
          </div>
        </Field>

        <Field label="Description" className="last-field">
          <textarea
            placeholder="What this community is for, and who should be in it."
            value={form.description}
            onChange={set('description')}
          />
        </Field>
      </ModalBody>

      <ModalFoot>
        <button className="btn btn-ghost" onClick={closeModal} disabled={saving}>
          Cancel
        </button>
        <button className="btn btn-primary" onClick={submit} data-busy={saving}>
          {saving ? 'Creating…' : 'Create community'}
        </button>
      </ModalFoot>
    </Modal>
  )
}
