const SIZES = { sm: 'avatar-sm', lg: 'avatar-lg', xl: 'avatar-xl' }

/**
 * Initials bubble, or a picture when there is one.
 *
 * `src` is optional and initials stay the fallback: a community with no logo,
 * and one whose logo fails to load, both land on the same bubble rather than an
 * empty circle. The gradient class is kept on the element either way so the
 * shape and size rules apply identically.
 */
export default function Avatar({
  initials, color = 'a1', size, className = '', src = null, alt = '', ...rest
}) {
  const classes = ['avatar', SIZES[size], color, className].filter(Boolean).join(' ')
  return (
    <div className={classes} {...rest}>
      {src
        ? <img className="avatar-img" src={src} alt={alt || initials} />
        : initials}
    </div>
  )
}
