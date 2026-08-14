# Deal Network — Backend

FastAPI + PostgreSQL API behind the React frontend in `../frontend`.

## Running

```bash
cd backend
venv/bin/pip install -r requirements.txt

venv/bin/python seed.py --reset          # demo data (optional)
venv/bin/uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health — reports which OAuth providers are live and
  whether SMTP is configured.

Tables are created automatically on startup. Alembic is installed for real
migrations once the schema settles.

```bash
venv/bin/python oauth_test.py            # 21 checks — OAuth endpoints
venv/bin/python communities_test.py      # 61 checks — communities, moderation, channels
venv/bin/python media_test.py            # 46 checks — uploads, attachments, Home rails
venv/bin/python terms_test.py            # 51 checks — the terms gate and what it records
venv/bin/python plans_test.py            # 53 checks — plan selection and the access gate
venv/bin/python onboarding_test.py       # 44 checks — profile setup and what it writes
venv/bin/python profile_test.py          # 37 checks — editing a profile, mandate and visibility
venv/bin/python entitlements_test.py     # 47 checks — what each plan unlocks, and what it blocks
venv/bin/python signout_test.py          # 38 checks — sign-out and token revocation
venv/bin/python smoke_test.py            # 71 checks — everything else
```

All ten need the server running. They are re-runnable: they create their own
fixtures, assert counts relative to a baseline, and clean up after themselves, so
they do not need a reseed between runs and will not trip over your own account.

## Configuration

Everything comes from `backend/.env` — see `.env.example` for the full list.

### OAuth

`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are **empty**, so Google sign-in is
switched off and `/auth/google/login` returns 503 until you fill them in. To enable:

1. Google Cloud Console → APIs & Services → Credentials → **Create OAuth client ID** → Web application.
2. Add `http://localhost:8000/auth/google/callback` under *Authorised redirect URIs* — it
   must match `GOOGLE_REDIRECT_URI` exactly.
3. Paste the client ID and secret into `.env` and restart.

Apple Sign In is implemented and stays disabled until `APPLE_CLIENT_ID`,
`APPLE_TEAM_ID`, `APPLE_KEY_ID` and `APPLE_PRIVATE_KEY` (the `.p8` contents) are set.
Apple posts its callback as a form, which is why that route is a POST.

`GET /auth/providers` returns only the configured providers, so the frontend can show
just the buttons that work.

### Sign-in flow

```
frontend  →  GET /auth/google/login          (backend redirects to Google)
Google    →  GET /auth/google/callback       (backend verifies state, exchanges code)
backend   →  302 FRONTEND_URL/auth/callback#access_token=…&refresh_token=…&new_user=true
```

Tokens come back in the URL **fragment**, which browsers never send to a server and
which stays out of referrers and access logs. The SPA reads `location.hash`, stores the
tokens and calls `/api/me`.

The `state` parameter is a signed, 10-minute JWT checked on the callback, so a forged
callback is rejected.

### Signing out

```
POST /auth/logout
Authorization: Bearer <access token>      (optional)
{ "refresh_token": "<refresh token>" }    (optional — but send it)
```

JWTs are self-contained, so a copy of one keeps working until it expires unless the
server is told otherwise. Sign-out writes the `jti` of every token presented to
`revoked_tokens`; `get_current_user` and `POST /auth/refresh` refuse anything listed,
and expired rows are purged on each call.

- **Authentication is optional on purpose.** You can only revoke a token you are
  holding, so the endpoint takes whatever the caller has — that way sign-out still
  kills the refresh token when the access token has already expired. Presenting
  nothing at all is the only 401.
- **Repeat calls are fine.** An expired, forged or already-revoked token needs no row,
  so signing out twice returns 200.
- **Only that session ends.** Other devices keep working; there is no global
  "sign out everywhere" yet — that wants a token version on `users`.

The SPA sends both halves and clears `sessionStorage` afterwards.

### SMTP

`SMTP_USER` / `SMTP_PASS` drive all outbound mail (Gmail on port 587, STARTTLS).
Emails sent: welcome on first sign-in, connection request, connection accepted,
introduction request, subscription confirmation. All are Jinja templates in
`app/templates/email/`.

Sending happens in a FastAPI background task and never raises into a request — if the
mail server is down, the API call still succeeds and the failure is logged.

## Endpoints

| Area | Endpoints |
| --- | --- |
| Auth | `GET /auth/providers`, `GET /auth/{provider}/login`, `GET /auth/google/callback`, `POST /auth/apple/callback`, `POST /auth/refresh`, `GET /auth/me`, `GET /auth/session`, `POST /auth/logout` |
| Terms | `GET /api/terms` (open), `POST /api/terms/accept`, `GET /api/terms/acceptance` |
| Profile setup | `GET /api/onboarding`, `POST /api/onboarding/role`, `POST /api/onboarding/profile` |
| Profile | `GET|PATCH /api/me`, `GET /api/me/stats`, `GET|PUT /api/me/visibility`, `GET|PUT /api/me/mandate` |

| Members | `GET /api/members` (filter by `role`, `q`), `GET /api/members/{id}` |
| Connections | `GET|POST /api/connections`, `POST /api/connections/{id}/accept`, `POST /api/connections/{id}/decline` |
| Communities | `GET|POST /api/communities` (filter by `kind`, `joined`, `q`), `GET|PATCH|DELETE /api/communities/{slug}`, `GET /api/communities/{slug}/members`, `POST /api/communities/{slug}/join`, `DELETE /api/communities/{slug}/leave` |
| Community moderation | `GET /api/communities/{slug}/requests`, `POST /api/communities/{slug}/requests/{user_id}/approve`, `POST /api/communities/{slug}/requests/{user_id}/decline` |
| Community channels | `GET|POST /api/communities/{slug}/channels`, `DELETE /api/communities/{slug}/channels/{channel_id}` |
| Feed | `GET|POST /api/posts`, `GET|DELETE /api/posts/{id}`, `POST /api/posts/{id}/like`, `GET|POST /api/posts/{id}/comments` |
| Media | `POST /api/media` (multipart `file`), `GET /api/media`, `DELETE /api/media/{id}`, files served at `/media/{stored_name}` |
| Home rails | `GET /api/me/stats`, `GET /api/communities/suggested`, `GET /api/members/suggested` |
| Contacts | `GET|POST /api/contacts`, `GET /api/contacts/pipeline`, `GET|PATCH|DELETE /api/contacts/{id}`, `PUT /api/contacts/{id}/stage` |
| Investors | `GET /api/investors/overview`, `GET|POST /api/investors/introductions`, `POST /api/investors/introductions/{id}/respond`, `POST|DELETE /api/investors/follow/{id}` |
| Plans | `GET /api/plans`, `POST /api/plans/select`, `GET /api/plans/selection`, `GET /api/plans/selections`, `GET /api/plans/subscription`, `POST /api/plans/subscribe`, `POST /api/plans/cancel` |
| Entitlements | `GET /api/plans/entitlements` (mine), `GET /api/plans/{plan}/entitlements` (any tier) |

Auth sits at `/auth` rather than `/api/auth` so the callback path matches
`GOOGLE_REDIRECT_URI` in `.env` without editing it.

## Layout

```
app/
  main.py               app, CORS, lifespan, health
  core/
    config.py           .env settings
    database.py         async engine, session, Base
    security.py         JWT issue/verify, signed OAuth state
  models/               SQLAlchemy models (+ shared enum instances in base.py)
  schemas/              Pydantic request/response models
  api/
    deps.py             DbSession, CurrentUser, OptionalUser
    router.py           mounts the /api routers
    routes/             auth, users, terms, plans, onboarding, communities, posts, media,
                        contacts, investors
  services/
    oauth.py            Google + Apple
    email.py            SMTP delivery and the message set
    storage.py          upload validation and disk writes
    users.py            provisioning a member from an OAuth profile
    tokens.py           the sign-out denylist (revoke, check, purge)
    terms.py            the terms text, its version, and who has accepted it
    onboarding.py       profile-setup options, and applying the answers
    entitlements.py     which modules and features each plan unlocks
  templates/email/      Jinja email templates
uploads/                uploaded files (git-ignored)
seed.py                 demo data matching the frontend
oauth_test.py           OAuth endpoint checks
communities_test.py     community, moderation and channel checks
media_test.py           upload, attachment and Home-rail checks
terms_test.py           the terms gate and what it records
onboarding_test.py      profile setup and what it writes
profile_test.py         editing a profile, mandate and field visibility
entitlements_test.py    what each plan unlocks, and what it blocks
plans_test.py           plan selection and the access gate
signout_test.py         sign-out and token revocation
smoke_test.py           everything else
```

## Notes on data handling

- **Two gates stand between signing in and the app, in this order.**

  ```
  sign in  ->  agree to the terms  ->  choose a plan  ->  set your profile up  ->  the product
  ```

  `require_terms_accepted` then `require_plan_selected`, applied together as
  `deps.GATES`. Only `/api/me`, `/api/terms` and `/auth/*` are reachable before the
  first; `/api/plans` opens after it. The API returns `403 {"detail": "terms_not_accepted"}`
  and then `403 {"detail": "plan_not_selected"}` — stable codes the SPA switches on. It
  mirrors both by locking navigation to `/terms` and then `/plans`, but the server is the
  enforcement point. Early access is selectable and free — the second gate is "choose",
  not "pay".
- **Every acceptance is recorded** in `terms_acceptances`: who (name and email snapshotted
  at the time), which `version`, both required consents stored separately, the optional
  marketing opt-in, and when. Rows are appended, so re-agreeing keeps the history. A member
  is past the gate when they have a row for `TERMS_VERSION` — bumping that constant in
  `services/terms.py` asks everyone again on their next visit. The text itself is served
  from there too, so an acceptance always refers to wording the server controls.
- **Profile setup is the last step**, and the only one the API does not refuse to serve
  around: `member_onboarding` holds one row per member, updated as they go, so a
  half-finished setup resumes rather than restarts. Step 1 writes the role straight onto
  the profile (it is useful for suggestions on its own); step 2 copies company, market,
  asset classes and description onto the `User` and mandate, and sets `onboarded`. The
  option lists live in `services/onboarding.py` and are served with the state, so the
  client offers exactly what the API will accept. The SPA locks navigation to
  `/onboarding` until `onboarded` is true — add `require_onboarded` to `deps.GATES` if
  that should be enforced server-side too.
- **Editing a profile is a PATCH of only what changed.** `PATCH /api/me` touches just the
  keys it is sent, so two edits from different screens cannot clobber each other. Text is
  trimmed, and a field cleared to blank is stored as NULL rather than `""` — "not set" has
  one representation. `name` is the exception: it has no blank state and a blank one is a
  422. The investor-facing half (markets, typical raise, stage) is `PUT /api/me/mandate`,
  and each profile field's Public/Members/Private choice is its own row via
  `PUT /api/me/visibility`.
- **A plan reaches up to a roadmap phase.** `services/entitlements.py` holds the module
  list from the landing page and how far each tier reaches: Early access phase 1,
  Member phase 3, Professional everything including the Pro-only module. A module counts
  as included once the plan reaches its *final* phase, so "Analytics · Phase 3–4" is
  Professional rather than Member — flip `_reaches` if it should unlock at its first
  phase instead. The same module maps the ticks on the plan cards to real limits: 25
  contacts on the free tier, and the pipeline board, community creation and introduction
  requests from Member up. Blocked calls return `403 {"detail": "upgrade_required"}` with
  `X-Required-Plan` and `X-Required-Feature` headers; hitting the contact ceiling returns
  `403 {"detail": "contact_limit_reached"}`.
- **Every plan choice is recorded** in `plan_selections`: who (name, email and company
  snapshotted at the time), which plan, its display name and price, the billing period,
  the timestamp, and whether it came from onboarding or a later change. Rows are appended,
  never overwritten, so the history is intact; exactly one carries `is_current`.
- **Contacts and pipeline are private.** Every query is scoped to `owner_id`; there is
  no endpoint that exposes one member's contacts to another. The smoke test asserts this.
- **Community discussions are members-only.** Reading a community feed, a single post,
  its comments, or liking it all require a joined `CommunityMember` row. The global
  feed returns unattached posts plus those from communities you have joined — never
  another community's discussion. `communities_test.py` covers each of these paths.
- **Uploads are allow-listed and content-checked.** `services/storage.py` accepts only
  JPEG/PNG/GIF/WebP/PDF/TXT/CSV/DOC(X)/XLS(X), verifies the file's magic bytes against
  the declared content type, refuses SVG outright (it can carry script), and stores under a
  random name so nothing user-supplied reaches the path. Size is capped twice: once by
  `BodySizeLimitMiddleware` *before* the body is parsed (a route-level check is too late —
  FastAPI spools the whole multipart body to disk before it resolves the auth dependency),
  and again while the file is read.
  Files are served from `/media` with `X-Content-Type-Options: nosniff` and a restrictive
  CSP. Only the uploader can attach a file to a post.
- **Media URLs are unguessable but unauthenticated.** Anyone with the random URL can
  fetch the file. That is fine for post images; it is *not* good enough for the private
  Data Room that is planned — that will need signed, expiring URLs.
- **`member_count` is updated in SQL**, not read-modify-written in Python, so two
  simultaneous joins cannot lose one another's increment. Note the seed data ships
  inflated counts (342 members against 3 real rows) deliberately, so the demo screens
  look realistic; real joins and leaves stay consistent from there.
- **Card details are not stored.** `POST /api/plans/subscribe` keeps only the last four
  digits and the cardholder name. Put a real PSP (Stripe) in front of this before taking
  live payments — the current endpoint does not charge anything.
- **Field visibility** is stored per field per user (`field_visibility`), with the eight
  keys the profile screen uses. The API records the choice; enforcing it when serving
  another member's profile is the next piece to build.

## Not built yet

`GET /api/members/{id}` returns the full profile regardless of the viewer's
relationship. The visibility levels are recorded but not yet applied as a filter on
outbound profile data — worth doing before the network is public.
