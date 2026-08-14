/** Labelled form control wrapper. Pass the input/select/textarea as children. */
export default function Field({ label, hint, className = '', children }) {
  return (
    <div className={['field', className].filter(Boolean).join(' ')}>
      {label && <label>{label}</label>}
      {children}
      {hint && <div className="hint">{hint}</div>}
    </div>
  )
}

export function FieldRow({ children, cols = 2 }) {
  return <div className={`field-row${cols === 3 ? ' field-row-3' : ''}`}>{children}</div>
}
