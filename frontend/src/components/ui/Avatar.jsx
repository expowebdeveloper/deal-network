const SIZES = { sm: 'avatar-sm', lg: 'avatar-lg', xl: 'avatar-xl' }

/** Initials bubble. `color` is one of the a1–a6 gradient classes. */
export default function Avatar({ initials, color = 'a1', size, className = '', ...rest }) {
  const classes = ['avatar', SIZES[size], color, className].filter(Boolean).join(' ')
  return (
    <div className={classes} {...rest}>
      {initials}
    </div>
  )
}
