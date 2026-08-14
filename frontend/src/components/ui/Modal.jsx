import { useApp } from '../../context/AppContext'

/**
 * Modal shell. Clicking the backdrop closes it; Escape is handled globally
 * in AppContext so every modal behaves the same way.
 */
export default function Modal({ width, className = '', children }) {
  const { closeModal } = useApp()
  const classes = [
    'modal',
    width === 'wide' && 'modal-wide',
    width === 'narrow' && 'modal-narrow',
    className,
  ].filter(Boolean).join(' ')

  return (
    <div className="modal-back" onClick={(e) => { if (e.target === e.currentTarget) closeModal() }}>
      <div className={classes}>{children}</div>
    </div>
  )
}

export function ModalHead({ children, className = '' }) {
  return <div className={['modal-head', className].filter(Boolean).join(' ')}>{children}</div>
}

export function ModalTitle({ title, sub, children }) {
  return (
    <div className="tt">
      <h2>{title}</h2>
      {sub && <p>{sub}</p>}
      {children}
    </div>
  )
}

export function ModalBody({ children, className = '' }) {
  return <div className={['modal-body', className].filter(Boolean).join(' ')}>{children}</div>
}

export function ModalFoot({ children, center = false }) {
  return (
    <div className={['modal-foot', center && 'modal-foot-center'].filter(Boolean).join(' ')}>
      {children}
    </div>
  )
}
