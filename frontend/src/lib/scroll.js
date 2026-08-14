/** Smooth-scroll to a section of the current page, by element id. */
export function scrollTo(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
}
