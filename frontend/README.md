# Deal Network — Frontend

React port of `../sample.html`. Same UI, same interactions, restructured into
components with the mock content pulled out into data modules.

## Running

```bash
npm install
npm run dev      # http://localhost:5174 — pinned; must match FRONTEND_URL and
                 # CORS_ORIGINS in backend/.env or OAuth sign-in fails
npm run build    # production build into dist/
npm run preview  # serve the production build
npm run lint
```

## Layout

```
src/
  main.jsx               entry — router + app provider
  App.jsx                routes, plus the overlay hosts
  context/AppContext.jsx auth, active modal, flow overlay, presenter drawer
  components/
    layout/              AppShell, Sidebar, Topbar, BottomNav, Screen
    screens/             one file per route
    modals/              one file per modal + ModalHost that picks between them
    flow/                the "How it connects" overlay
    presenter/           presenter notes drawer
    ui/                  Avatar, Tag, Chip, Field, Facepile, Modal
    icons/Icons.jsx      every SVG in the app
  data/                  all mock content — swap these for API calls
  styles/                the sample's CSS, split by section
```

## Routes

| Path | Screen |
| --- | --- |
| `/` | Home feed |
| `/communities` | Communities |
| `/members` | Members |
| `/investors` | Investors |
| `/contacts` | Contacts (list + pipeline board) |
| `/` (signed out) | Landing page — hero, modules, roadmap, ported from `../landing.html` |
| `/login` | Sign in with Google or Apple |
| `/terms` | Terms consent — the gate between sign-in and plans |
| `/plans` | Plans |
| `/onboarding` | Profile setup — role picker, then company details |
| `/profile` | Profile + field visibility |

The profile page is live throughout: **Edit profile** saves through `PATCH /api/me` and
`PUT /api/me/mandate`, the visibility rows show the real profile rather than samples, and
each row's Public / Members / Private choice persists via `PUT /api/me/visibility`.

A signed-out visitor gets the public landing page at `/`; every call to action on
it leads to `/login`, where the OAuth buttons are. Its content lives in
[`src/data/landing.js`](src/data/landing.js) and its styles in
[`src/styles/landing.css`](src/styles/landing.css) — the design system itself
(tokens, buttons, chips, cards, modal) is shared with the app, so only the
landing-specific layout is new.

Sign-in is real: the OAuth buttons hand off to the backend, which redirects back
to `/auth/callback` with the token pair in the URL fragment. Tokens live in
`sessionStorage`, so a refresh or a deep link holds and a new tab starts at the
sign-in screen.

**Where sign-in lands you.** Two steps stand between signing in and the feed, and
sign-in drops you on the first one still outstanding:

```
sign in  ->  /terms       agree to them (both required boxes)
         ->  /plans       choose a tier
         ->  /onboarding  role, then company details
         ->  /profile     what you just set up, and the app is open
```

The app is locked to each step until it is done. The API enforces the first two,
returning `terms_not_accepted` and then `plan_not_selected`; profile setup is
recorded server-side (`/api/onboarding`) and locked in the router. Once all three
are behind you, sign-in goes straight to the feed and `/plans` becomes an ordinary
screen you can open to change tier.

`signOut()` calls `POST /auth/logout` so the backend revokes the tokens, then
clears `sessionStorage`. If the API is unreachable the local session is dropped
anyway.

## Differences from sample.html

Two deliberate changes, both fixes rather than redesigns:

1. **Modal stacking.** The sample put `.modal-back` at `z-index:150`, below the
   login screen (200) and the flow overlay (160) — so modals opened from either
   were invisible. Raised to 220.
2. **Real URLs.** Screens are routes instead of `display:none` toggles, which is
   what makes the `sessionStorage` session above necessary.

One thing kept as-is on purpose: community cards use `ccard` *without* the
`card` base class, exactly as in the sample, so they have no white background.
Add `card` alongside it if that was unintended.

## Wiring up a backend

Everything under `src/data/` is plain exported objects with no React in them.
Replace each module with a fetch (or a hook) and the components keep working —
they only read the shapes those files define.
