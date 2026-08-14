/** Small pill label. `variant` maps to the tag-* colour classes. */
export default function Tag({ variant, className = '', children, ...rest }) {
  const classes = ['tag', variant && `tag-${variant}`, className].filter(Boolean).join(' ')
  return (
    <span className={classes} {...rest}>
      {children}
    </span>
  )
}
