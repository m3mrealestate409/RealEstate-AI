# Frontend

The staff/admin interface is a React 18 single-page app built with Vite 6. It is
served as static assets (separate from the API). A second, standalone artifact —
the embeddable `widget.js` — is served by the backend and documented in
[integrations.md](integrations.md).

## Stack

| Concern | Choice |
|---|---|
| Framework | React 18 (`react`, `react-dom` ^18.3) |
| Build/dev | Vite 6 (`npm run dev` / `build` / `preview`) |
| Routing | `react-router-dom` ^6.28 |
| Markdown | `react-markdown` ^10 (no raw HTML — safe by default) |
| Styling | a single hand-written `src/styles.css` (no CSS framework) |
| State | React hooks + a small `AuthContext`; server data fetched per-view |

## Structure

```
frontend/src/
  main.jsx              app bootstrap
  App.jsx               routes (react-router) + <Protected> guard
  styles.css            all styling (light/dark aware)
  api/client.js         fetch wrapper: base URL, Bearer header, blob downloads
  auth/AuthContext.jsx  login/logout, current user, token persistence
  components/
    Layout.jsx          sidebar shell, nav, the super-admin alerts bell
    Icons.jsx           inline SVG icon set
    Logo.jsx            brand mark
    BlockRenderer.jsx   renders answer "blocks" (tables, cards, markdown)
    Citations.jsx       source citations under answers
  pages/
    Login.jsx           auth
    Query.jsx           "Ask" — the assistant chat
    Projects.jsx, ProjectDetail.jsx
    Calculators.jsx
    Dashboard.jsx       analytics
    Knowledge.jsx, AiImport.jsx
    LiveChat.jsx        agent console + human takeover
    Admin.jsx           the admin console (category → sub-tab navigation)
    Integrations.jsx    channels, API keys, lead webhook, assistant, notifications
    Billing.jsx         Plan & Usage / Payments / Pricing
    Platform.jsx        super-admin: organizations, plans, alerts
    AiSettings.jsx      super-admin: LLM provider + key
    SystemHealth.jsx    service health panel
```

## Routing & guards

- `App.jsx` defines routes; `<Protected>` redirects unauthenticated users to
  `/login`. Role-specific pages (Platform, Admin) also check `role` /
  `is_super_admin` from the current user.
- **Server-side authorization is authoritative.** Client-side gating only hides
  UI; every privileged call is enforced by the API (see [security.md](security.md)).

## Authentication in the client

- `AuthContext` calls `POST /v1/auth/login`, stores the JWT, and exposes the
  current user. The token is attached as `Authorization: Bearer` by
  `api/client.js`. A `401` clears the session and returns to `/login`.
- The token is kept in `localStorage` (see [security.md](security.md) and
  [roadmap.md](roadmap.md) for the trade-off and the HttpOnly-cookie follow-up).

## Rendering answers

- The **Ask** page requests `format: "blocks"`; `BlockRenderer` renders each
  block type (price tables, config/inventory cards, timelines, paragraphs) so
  figures display exactly. Prose blocks go through `react-markdown` (raw HTML
  disabled, so DB/LLM markdown cannot inject script).
- The public widget uses humanized *text* instead of blocks (see
  [rag-pipeline.md](rag-pipeline.md)).

## Configuration

- Only `VITE_API_URL` (the backend base URL) is read at build time and is the
  **only** value that reaches the browser bundle. No secret is ever bundled.
- Build outputs static assets; serve them behind a CDN / web server in
  production (see [deployment.md](deployment.md)). Vite emits **no** source maps
  for `build` by default.

## Local development

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies to VITE_API_URL (default :8001)
```

## Admin console navigation model

`Admin.jsx` groups features into **categories** (Growth · Projects & Data ·
Knowledge · Team · Assistant · Integrations · Billing · System); each category
has sub-tabs. This keeps ~30 admin functions discoverable. See
[admin-guide.md](admin-guide.md) for what each does.
