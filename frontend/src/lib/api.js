/**
 * Thin API client for the FastAPI backend.
 *
 * Tokens live in sessionStorage: a refresh or deep link keeps you signed in,
 * a new tab starts at the sign-in screen. On a 401 the client tries the refresh
 * token once, then replays the original request.
 */

export const API_URL = (
  import.meta.env.VITE_API_URL ||
  (typeof window !== 'undefined' && window.location.port === '5176'
    ? `${window.location.protocol}//${window.location.hostname}:8002`
    : 'http://localhost:8000')
).replace(/\/$/, '')

const ACCESS_KEY = 'dn.accessToken'
const REFRESH_KEY = 'dn.refreshToken'

/**
 * Thrown for any non-2xx response. `status` lets callers branch on 401/503.
 *
 * `headers` is kept because the API puts the *reason* for a refusal there —
 * X-Required-Plan, X-Contact-Limit, X-Community-Limit — so a message can name
 * the plan that lifts a limit instead of guessing. Those names are listed in
 * `expose_headers` on the backend's CORS config; without that a browser cannot
 * read them at all.
 */
export class ApiError extends Error {
  constructor(message, status, body, headers = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
    this.headers = headers
  }
}

function read(key) {
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key, value) {
  try {
    if (value) sessionStorage.setItem(key, value)
    else sessionStorage.removeItem(key)
  } catch {
    /* private mode — requests still work for this page load */
  }
}

export const tokens = {
  get access() {
    return read(ACCESS_KEY)
  },
  get refresh() {
    return read(REFRESH_KEY)
  },
  set({ access_token, refresh_token }) {
    write(ACCESS_KEY, access_token)
    write(REFRESH_KEY, refresh_token)
  },
  clear() {
    write(ACCESS_KEY, null)
    write(REFRESH_KEY, null)
  },
}

async function parse(response) {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function messageFrom(body, fallback) {
  if (!body) return fallback
  if (typeof body === 'string') return body
  // /api/v1 answers {"error": {code, message, details}}; the pre-v1 routes
  // answer {"detail": "..."}. Both reach here.
  if (typeof body.error?.message === 'string') return body.error.message
  if (typeof body.detail === 'string') return body.detail
  // FastAPI validation errors come back as a list of {loc, msg}.
  if (Array.isArray(body.detail)) {
    return body.detail.map((d) => d.msg).filter(Boolean).join(', ') || fallback
  }
  return fallback
}

async function rawRequest(
  path, { method = 'GET', body, auth = true, headers = {}, signal } = {},
) {
  // `signal` lets a caller cancel an in-flight request. The search box needs it:
  // it fires per keystroke, and without cancellation a slow early response can
  // land after a fast later one and overwrite fresher results.
  const init = { method, headers: { ...headers }, ...(signal ? { signal } : {}) }

  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }
  if (auth && tokens.access) {
    init.headers.Authorization = `Bearer ${tokens.access}`
  }

  let response
  try {
    response = await fetch(`${API_URL}${path}`, init)
  } catch (error) {
    // A cancelled request is not a failure — re-throw so callers can ignore it
    // rather than showing "cannot reach the API" for their own abort.
    if (error?.name === 'AbortError') throw error
    throw new ApiError(`Cannot reach the API at ${API_URL}. Is the backend running?`, 0, null)
  }

  const payload = await parse(response)
  if (!response.ok) {
    throw new ApiError(
      messageFrom(payload, response.statusText), response.status, payload, response.headers,
    )
  }
  return payload
}

/** Refresh once, and share the in-flight attempt between concurrent 401s. */
let refreshing = null

export async function refreshSession() {
  const refresh_token = tokens.refresh
  if (!refresh_token) return false

  refreshing ??= rawRequest('/auth/refresh', {
    method: 'POST',
    body: { refresh_token },
    auth: false,
  })
    .then((pair) => {
      tokens.set(pair)
      return true
    })
    .catch(() => {
      tokens.clear()
      return false
    })
    .finally(() => {
      refreshing = null
    })

  return refreshing
}

export async function request(path, options = {}) {
  try {
    return await rawRequest(path, options)
  } catch (error) {
    const retryable = error instanceof ApiError && error.status === 401 && options.auth !== false
    if (!retryable || options._retried) throw error

    const ok = await refreshSession()
    if (!ok) throw error
    return rawRequest(path, { ...options, _retried: true })
  }
}

export const api = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  delete: (path, options) => request(path, { ...options, method: 'DELETE' }),
}

/* --- Auth ---------------------------------------------------------------- */

/** Which sign-in buttons the backend can actually service right now. */
export function fetchProviders() {
  return request('/auth/providers', { auth: false })
}

/** Full-page handoff to the backend, which redirects on to the provider. */
export function startOAuth(provider) {
  window.location.href = `${API_URL}/auth/${provider}/login`
}

export function fetchMe() {
  return request('/api/me')
}

/**
 * Sign out: ask the backend to revoke this session's tokens, then drop them.
 *
 * Deliberately `rawRequest` and not `request` — a 401 here must not kick off the
 * refresh dance, which would mint a fresh pair and leave the member signed in.
 * The refresh token goes in the body because it is the half that would otherwise
 * outlive the access token. Local tokens are cleared even if the call fails.
 */
export async function logout() {
  const refresh_token = tokens.refresh
  try {
    if (tokens.access || refresh_token) {
      await rawRequest('/auth/logout', { method: 'POST', body: { refresh_token } })
    }
  } finally {
    tokens.clear()
  }
}
