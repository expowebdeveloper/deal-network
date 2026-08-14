/** Filter pill. `on` renders the selected (dark) state. */
export default function Chip({ on = false, className = '', children, ...rest }) {
  return (
    <button type="button" className={['chip', on && 'on', className].filter(Boolean).join(' ')} {...rest}>
      {children}
    </button>
  )
}
