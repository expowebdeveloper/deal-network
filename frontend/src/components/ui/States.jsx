/** Loading / empty / error blocks shared by the data-backed screens. */

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="state-block" role="status">
      <span className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  )
}

export function Empty({ title, children, action }) {
  return (
    <div className="state-block">
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  const message =
    error?.status === 0
      ? 'Cannot reach the API. Is the backend running on port 8000?'
      : error?.message || 'Something went wrong.'
  return (
    <div className="state-block state-error" role="alert">
      <h3>Could not load</h3>
      <p>{message}</p>
      {onRetry && (
        <button className="btn btn-ghost btn-sm" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}
