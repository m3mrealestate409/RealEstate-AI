# Changelog

All notable changes to the Chaahat Homes AI Knowledge Engine are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/); this
project uses [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH).

## [Unreleased]

## [2.6.3] — 2026-07-14

### Fixed — Live Chat fits the screen
- The console now sizes itself to the viewport instead of a fixed height, so
  the **Take over / reply bar is always visible on screen** — no page scrolling
  needed. Only the message list scrolls (like a real chat app).

## [2.6.2] — 2026-07-14

### Changed — Premium Live Chat console UI
Full visual redesign of the Live Chat page for a polished, luxury feel.

- **Inbox** — visitors get friendly names ("Visitor 5FDK") with colorful
  gradient avatars (consistent per visitor), presence dot with a soft pulse,
  relative times ("2m ago"), message previews, AI/agent pills, and a
  "Conversations" header with a live count badge.
- **Conversation** — chat-app style: avatars beside every bubble (visitor /
  ✦ AI / agent initial), soft gradient bubbles with per-role colors, timestamps
  under each message, elegant divider lines for system notes, and a refined
  header (avatar + name + "Online now" pulse).
- **Actions** — gradient "🎧 Take over this chat" button (greyed when the
  visitor left), pill composer with a circular gradient send button, and a
  subtle "↩ Return to AI" link.
- Beautiful empty states for both panels.

## [2.6.1] — 2026-07-13

### Added — Live Chat visitor presence
- **Online indicator** — a green dot shows which website visitors are currently
  on the page (grey when they've left), in the inbox and the conversation header.
  Driven by the widget's ~3s poll heartbeat (online = seen in the last 30s).
- **Take over disabled when the visitor left** — the button fades to
  "Visitor offline — can't take over" once they're gone, so agents don't try to
  jump into a dead chat.

## [2.6.0] — 2026-07-13

### Added — New-chat notifications (Live Chat Phase 2), provider-agnostic
Get pinged the moment a new visitor starts chatting, so someone can jump in.

- **One system, any provider** — Admin → Integrations → **New-chat notifications**:
  - **Telegram** (recommended) — free, official, no ban risk: paste a bot token
    + chat id.
  - **Webhook** — POST to ANY URL with a caller-defined JSON body (with a
    `{{text}}` placeholder) + custom headers. Covers an unofficial WhatsApp HTTP
    service, the WhatsApp Cloud API (graph URL + Bearer header), Zapier/Make/n8n,
    Slack/Discord — anything. Switch provider anytime without code changes.
- **Fires once per new visitor** — on their first message only, not follow-ups.
- **Best-effort + non-blocking** — sent in the background; a notification
  failure never affects the visitor's chat.
- **Send test** button to verify the setup instantly.

## [2.5.1] — 2026-07-13

### Changed — Live Chat access control
- **Live Chat is now its own top-level page** (sidebar → 💬 Live Chat), not an
  Admin sub-tab.
- **Per-employee access** — admins always have Live Chat; an admin grants it to
  specific employees from Admin → **Users** (new "Live Chat" toggle). Sales staff
  without access can't see the page or call the endpoints (403).
- Login now returns `can_live_chat`; a new `require_live_chat` guard protects
  every console endpoint.

## [2.5.0] — 2026-07-13

### Added — Live chat with human takeover (Phase 1)
An employee can now watch website conversations in real time and jump in.

- **Live Chat console** — Admin → **💬 Live Chat**: an inbox of active website
  conversations (auto-refreshing), each showing the live transcript (visitor +
  AI). Click **Take over** to reply as a human — the AI pauses for that visitor
  until you hand it back with **Return to AI**.
- **Widget takeover UX** — when an agent takes over, the visitor sees
  "You're now chatting with {agent}", the agent's replies appear inline, and
  their own messages go straight to the agent (the AI stays silent). When the
  agent releases, "the assistant is back" and the AI resumes.
- **Every widget conversation is recorded** (`ChatSession` + `ChatMessage`),
  powering the console and polled by the widget (~3s) for near-real-time
  delivery — no WebSocket needed.

_Phase 2 (new-visitor notifications) coming next._

## [2.4.0] — 2026-07-13

### Added — Premium widget identity
- **Assistant name + profile photo** — set the assistant's display name and
  upload a profile picture in Admin → Integrations. Shown in the chat widget
  header (with an initials avatar fallback when no photo is set). Delivered via
  `/v1/widget/config` so the widget picks it up live.
- **Redesigned widget header** — avatar + name + an "Online" status, for a
  polished, branded look.
- **Premium callback button** — replaced the plain "📞 Callback" text with a
  clean pill button (proper phone icon + label, subtle hover).

## [2.3.1] — 2026-07-13

### Changed
- **Widget quick-reply chips** no longer appear under the first greeting — they
  now show only after an answer (from the 2nd message on), using the engine's
  context-aware suggestions.

## [2.3.0] — 2026-07-13

### Added — Abuse protection for the public chat widget
The public website widget now has its own guards so a bad actor can't flood it,
run up AI cost, or starve real employees. All Redis-backed and fail-open.

- **Rate limit (anti-flood)** — per chat session (20 / 5 min) and per IP
  (40 / 5 min) on `/v1/query` and `/v1/leads`. Over the limit returns HTTP 429;
  the widget shows a friendly "please wait a moment" message. Employees (JWT)
  are unaffected.
- **Daily cost ceiling** — each org's widget has its own daily budget of
  expensive (LLM) queries (default 300). When spent it **degrades** rather than
  errors: prices/plans/amenities (from the database) keep working, and other
  questions get a warm "high demand — leave your number" reply that offers a
  callback (turning the limit into a lead).
- **Separate budgets** — widget traffic now counts against its **own** budget,
  not the employee/company quota, so public abuse can never block staff.



### Added
- **Leads: "Interested in" column** — the project a lead was viewing/discussing
  (auto-detected from the chat) now shows in its own column, instead of being
  hidden behind the message text.
- **Delete a lead** — a Delete button on each row (and `DELETE /v1/admin/leads/{id}`)
  so admins can remove test or junk leads without touching the database.

## [2.2.1] — 2026-07-13

### Fixed
- **Chat phone → lead missed some formats** — the auto-lead phone detector only
  matched a couple of number groupings, so a visitor typing e.g. `9876 543210`
  or `987-654-3210` was not captured. It now strips separators first and catches
  any grouping (spaces, dashes, dots, `+91`/`0` prefix), while still ignoring
  ordinary numbers in questions (prices, areas, budgets).

## [2.2.0] — 2026-07-13

### Added — Smarter chat experience (website widget)
- **Auto-lead from chat** — when a website visitor types their phone number in
  the chat, the engine captures a lead instantly (with the project they were
  discussing) and replies with a warm confirmation. Only external channels
  (API key) trigger this — a logged-in employee typing a number never creates a
  lead.
- **Callback form auto-opens** — when the visitor asks to be contacted / book a
  visit (or when we couldn't answer), the callback form surfaces automatically.
  A `suggest_callback` signal drives it; the persona verbally offers, the UI
  opens the form.
- **Quick-reply chips** — the widget shows tappable chips: default ones after
  the greeting (Price / Payment plan / Amenities / Book a visit) and
  context-aware follow-ups (from the engine's `suggestions`) after each answer.
- **Typing reveal** — bot answers stream in word-by-word for a live feel. It's
  purely cosmetic and decoupled from logic, so chips/forms still work instantly
  even if the tab is backgrounded.

### API
- `POST /v1/query` responses now include `suggest_callback` and `lead_captured`
  flags (for any chat channel to react to).

## [2.1.1] — 2026-07-13

### Fixed
- **Website widget "Send" broken** — the new lead (Callback) form added inputs
  and buttons that appear before the message composer in the DOM, so the widget
  grabbed the wrong element and clicking Send did nothing. Selectors are now
  scoped to the footer.
- **Frontend request timeout** — every API call now has a 45s hard timeout
  (AbortController). Previously a hung/restarting backend left the request
  pending forever, so the "Ask" button stayed disabled until a page reload.

## [2.1.0] — 2026-07-13

### Added — Lead capture, CRM push & Insights
The assistant now turns conversations into **sales leads** and shows admins
what customers are actually asking.

- **Lead capture** — the website chat widget has a **📞 Callback** button that
  collects a prospect's name, phone and message. Leads are stored per-org and
  can arrive from any channel via `POST /v1/leads` (API key auth).
- **CRM webhook** — Admin → **Leads** lets an org set a webhook URL; every new
  lead is POSTed there in real time (best-effort, non-blocking) so it lands in
  the company's own CRM. Provider-agnostic — works with any endpoint.
- **Leads tab** — Admin → **📇 Leads** lists captured prospects with clickable
  phone links and a status pipeline (new → contacted → qualified → closed).
- **Insights dashboard** — Admin → **📊 Insights** shows total/today/unanswered
  KPIs, the **top unanswered questions grouped by frequency** (so you know
  exactly which data or brochure to add next), most-asked projects, and a
  7-day question trend.

### Added — Assistant persona & conversation memory
- **Org-wide assistant persona** — Admin → **Integrations** lets an org set a
  master prompt (identity, voice, style) applied to **every channel** (web app,
  website widget, CRM, WhatsApp). It changes tone only; the grounding rules
  (never invent facts) always stay on top.
- **Per-session conversation memory** — the assistant now remembers the last
  few turns (question **and** answer) so it can reference earlier context
  naturally ("summarise what we discussed"). Memory is scoped to the
  authenticated user/session; facts are still re-fetched, never cached as truth.
- **Widget session continuity** — the chat widget keeps one session across page
  navigations and restores the visible conversation, so follow-ups work as the
  visitor browses the site.

### Added — Embeddable chat widget & integration guides
- **Embeddable widget** — `‹script src=".../static/widget.js"›` drops a themed
  chat bubble on any site (WordPress, custom). Configured via data-attributes
  (title, accent, API key); served with `no-cache` so updates roll out live.
- **Editable widget greeting** — org admins can set the teaser/first-message
  greeting; the widget picks it up with no code change.
- **Integrations tab** — Admin → **🧩 Integrations** gives step-by-step setup
  guides per channel (WordPress, Website/CRM API), extensible as channels grow.

### Fixed
- Widget loading indicator now shows animated typing dots instead of literal
  escaped HTML.

## [2.0.0] — 2026-07-12

### Added — API-first integration layer (V2 · Phase 1)
The engine can now be connected to external systems — your **CRM, a WhatsApp
bot, a voice agent, or any website** — via a stable, documented API.

- **API keys** — Admin → **API Keys** lets an org admin create permanent,
  revocable keys (the full key is shown once). Send `X-API-Key: px_...` on any
  endpoint. A key is **tenant-scoped** (only ever sees its own organization's
  data) and acts as its admin creator — no 8-hour token expiry to manage.
- **Query response formats** — `POST /v1/query` accepts `format`: `blocks`
  (rich, default), `text` (plain), or `voice` (short, spoken, no Markdown).
  Every response now includes a ready-to-use **`answer_text`** string.
- **Integration guide** — `INTEGRATION.md` documents auth, the query endpoint,
  formats and examples; the full auto-generated reference stays at `/docs`.

## [1.23.0] — 2026-07-12

### Security / multi-tenancy
- **Audit log is now org-scoped** — a company (org) admin sees only actions by
  users in their own organization; the super-admin still sees everything.
- **AI Settings (Gemini config) is now super-admin only** — the tab is hidden for
  org admins and the settings endpoints require super-admin, so tenant admins
  can no longer view or change the global AI provider/key.

## [1.22.0] — 2026-07-11

### Changed — Cleaner document answers
- When the AI writes a **summary**, the raw brochure excerpt is no longer shown
  as a separate block — the formatted summary plus the cited source already
  cover it (the retrieved text is still used for grounding and citations).
- When a document answer has **no summary** (e.g. specifications), the retrieved
  brochure text is now broken into **bullet points** instead of one run-on line.

### Added — Query length limit
- Queries are capped at **1000 characters** (backend validation + a frontend
  input limit and near-limit counter), so a large pasted block can't inflate
  LLM / embedding token cost. Real questions are far shorter, so this is
  invisible in normal use.

## [1.21.0] — 2026-07-11

### Changed — Better-reading LLM answers
- **Markdown is now rendered** in AI summaries / general-knowledge answers, so
  bold, bullet points and headings display properly instead of showing raw `**`
  and `*` characters (via `react-markdown`; frontend-only, no token cost).
- **Rewrote the system prompt** for tone and readability: the assistant opens
  with a one-line hook, then gives short bullet points with the key term bolded,
  matches the user's language (English/Hindi/Hinglish), and stays concise. All
  grounding rules are unchanged (uses only retrieved facts, never invents
  figures, exact "not available" fallback).

## [1.20.0] — 2026-07-11

### Added — Share brochure / cost sheet on WhatsApp
- Each document (brochure and cost sheet) now has a **Share** action on the
  project page. On mobile it shares the actual PDF via the native share sheet
  (WhatsApp included); on desktop it downloads the PDF and opens WhatsApp Web
  with a prefilled message. No public link — the auth-protected PDF is fetched
  by the app first.

### Changed — Project page layout & performance
- **Documents panel** — brochure + cost sheet are grouped in one clean card
  (brochure on top). On **desktop** it sits at the top-right of the header; on
  **mobile** it stacks below. The share control is an icon.
- **Faster AI answers** — switched the default LLM to `gemini-flash-lite-latest`,
  which has "thinking" **off** by default. Real answers dropped from ~6 s (often
  truncated) to ~1.4 s and are complete. This engine's LLM work is simple and
  grounded, so extended reasoning isn't needed. The model is changeable anytime
  from Admin → AI Settings.

### Fixed
- **Brand logo disappearing** — the PropX monogram renders twice per page (mobile
  top bar + sidebar) and both used the same SVG gradient IDs; duplicate IDs made
  the browser resolve the wrong gradient and blank out the logo. Gradient IDs are
  now unique per instance (via `useId`).

## [1.19.0] — 2026-07-11

### Added — Amenities are now SQL-first
- Amenities/facilities are extracted **once** from the brochure at AI-import time
  and stored in the database, then always served from SQL — the LLM is never hit
  for an amenities query again (previously every amenities question ran RAG +
  LLM). New `amenities` table; a query like "amenities" now answers from the DB
  (handler `database`, confidence 0.98), grouped by category.
- AI Import extracts amenities into the editable draft; **Manage Data → Amenities**
  lets you add / categorise / delete them; the project page shows an Amenities
  section (SQL) grouped by category.
- Note: amenities now come from the DB only — existing projects need amenities
  populated (re-run AI Import or add them under Manage Data → Amenities).

### Added — Multiple cost sheets with titles
- A project can have **multiple cost sheets**, each with its own title. They
  appear in a **dropdown** on the project page for viewing/download. Manage Data
  → Cost Sheet lists them with View/Delete and a title field on upload.

### Added — Rise type, launch price/year
- Projects have a **rise type** (High/Mid/Low Rise) shown as a small badge next
  to the title, and a **launch price** + **launch year** shown in a highlighted
  strip. Launch price is hidden behind an eye toggle (click to reveal). All three
  are editable under Manage Data → Project Details.

### Changed
- **"Carpet area" → "Size"** everywhere (uses super area); the separate carpet
  field is removed from all forms, tables and AI extraction.
- **Price table**: the plan column shows **"BSP"** (instead of "Base (all
  plans)"), and columns are reordered to `Configuration · Plan · Base Price ·
  Size · Unit · PLC · GST%` so Size and Unit sit together.
- **Project page header**: the status chip sits next to the rise-type badge; the
  View Brochure / cost-sheet controls are right-aligned; the cost-sheet dropdown
  and its View button are joined inside one border.

## [1.18.0] — 2026-07-11

### Added — Per-payment-plan pricing
- The **same configuration can now have a different price per payment plan**
  (real estate: e.g. Down-Payment is cheaper than CLP or Subvention). Each
  config keeps a **base price** (applies to all plans) plus optional **per-plan
  overrides**. A plan override supplies only the rate — PLC and GST are inherited
  from the base price.
- **Admin → Manage Data → Update Price / Stock**: a "For plan" selector lets you
  set the base price or a specific plan's price; existing plan prices show as
  chips on each configuration.
- The query engine and the project page now show a plan-wise price table
  (Configuration · Plan · Price…). Recommendations use the base price (falling
  back to the cheapest plan price).
- Backward compatible: all existing prices become the base price automatically.

### Added — Delete payment plans
- Payment plans can now be **deleted** (previously only added). Admin → Manage
  Data → Add Payment Plan lists existing plans with a Delete button.
- Deleting a plan also removes any prices set only for that plan (those configs
  revert to their base price); the confirmation dialog states this.

## [1.17.0] — 2026-07-11

### Security — production-grade audit, Critical + High fixes

A full security audit was performed. The 2 Critical and 3 High findings are
fixed and verified (all 13 tests pass); remaining Medium/Low items are tracked
for a follow-up hardening pass.

- **[Critical] JWT secret hardening** — the app now **refuses to start in
  production** (`APP_ENV` != development) with a weak or default `SECRET_KEY`
  (min 32 chars). Prevents forged super-admin tokens if a deployment shipped the
  default secret.
- **[Critical] Upload path-traversal → RCE** — uploaded file names are no longer
  used to build server paths. A new safe handler (`app/core/uploads.py`) writes
  to a server-generated UUID name, accepts **PDF only**, enforces a **25 MB**
  size cap, and verifies the path stays inside the uploads directory. Applied to
  brochure, cost-sheet, and replace-document uploads.
- **[High] Cross-tenant isolation on the query path** — conversation/session
  memory is now bound to the authenticated user (not just the client-supplied
  `session_id`), and every resolved project is **re-validated against the
  caller's organization** before any SQL/RAG lookup. Closes a cross-tenant read
  via session fixation.
- **[High] Default credentials** — removed the pre-filled demo email/password
  and the on-screen "Demo:" hint from the login page; the seeder now **refuses to
  create default-password admin/super-admin accounts in production**.
- **[High] Dev config in production** — added `entrypoint.prod.sh` (no
  `--reload`, multiple workers) and `docker-compose.prod.yml` (no source
  bind-mount, `APP_DEBUG=false`). CORS now uses an explicit `CORS_ORIGINS`
  allow-list in production (wildcard only in local debug, without credentials).

### Notes
- `.env.example` documents the new production variables (`APP_ENV`, `SECRET_KEY`,
  `CORS_ORIGINS`, `SEED_*`).
- Reminder: `init_db` migrations run at container **start** only — restart the
  API container after adding schema changes.

## [1.16.0] — 2026-07-11

### Added — Internet fallback (unverified)
- When the company knowledge base has **no answer**, the engine now falls back to
  the LLM's general knowledge instead of a dead-end "not available" — so the user
  still gets something.
- Such answers are clearly flagged: a red **"🌐 Internet · Not confident"** chip
  plus a warning banner ("not from your data … verify before sharing, especially
  prices"). The prompt instructs the AI to never invent precise figures.
- Verified answers from your SQL/RAG data are unchanged (no badge). The fallback
  needs a real LLM provider (skipped in mock mode) and counts against quota.



### Added
- **Bulk AI Import** — the AI Import tab now takes multiple brochure PDFs at once.
  Each becomes a draft in a review queue: assign it to a project, extract, review
  and edit, then Save — one at a time. Nothing is stored until you Save each
  (extraction runs sequentially to respect AI rate limits). Single-file import
  still works the same way.
- **Sample CSV download** — the Import CSV tab has a "Download sample CSV" button
  with the correct columns and example rows.

## [1.14.0] — 2026-07-11

### Added — Location & connectivity
- **Structured location points** per project — each a category (**Nearby /
  Connectivity / Upcoming Development**), a place name, and an optional distance.
  Managed under Admin → Manage Data → Location.
- Project page shows a grouped **"Location & Connectivity"** section.
- Query engine answers location questions ("what's nearby", "connectivity",
  "upcoming development") from SQL.
- **AI Import** now also extracts location points from the brochure's
  location/connectivity section into the editable preview.
- Endpoints: `GET/POST /v1/admin/projects/{id}/location`, `DELETE /v1/admin/location/{id}`,
  `GET /v1/projects/{id}/location` — org-scoped.

## [1.13.1] — 2026-07-11

### Changed
- Renamed "Builder" to **"Developer"** across the UI (real-estate wording).
  Internal tables are unchanged.

### Added
- **Delete a developer** — Admin → Developers now has a Delete action. Deletion
  is blocked with a clear message if any project still uses that developer
  (`DELETE /v1/admin/builders/{id}`, org-scoped).

## [1.13.0] — 2026-07-11

### Added — Project ↔ builder
- **Choose a builder per project** — the New Project and Project Details forms
  now have a Builder dropdown (org's builders + "None").
- The project page shows **"🏗️ by {builder}"** at the top.
- Project detail/list responses include `builder_id` and `builder_name`.

### Changed
- **Builders are now organization-scoped** — each tenant sees and picks only its
  own builders (previously global). Existing builders migrate to the default org.
  A project can only be assigned a builder from its own organization.

## [1.12.1] — 2026-07-11

### Fixed
- **Mobile & tablet navigation** — on narrow screens the sidebar was hidden with
  no way to navigate. Added a top bar with a hamburger that opens the sidebar as
  a slide-in drawer (with backdrop); tapping a link navigates and closes it.
  Desktop is unchanged.

## [1.12.0] — 2026-07-11

### Added — Cost sheet
- **Cost Sheet** (optional) — Admin → Manage Data → Cost Sheet lets an admin
  upload a project's cost-sheet PDF. It is stored for viewing/download only and
  is **not** indexed into RAG (pricing stays in SQL, §6).
- The project page now shows a **View Cost Sheet** button next to View Brochure
  (inline viewer + download), when a cost sheet exists.
- Endpoints: `POST /v1/admin/projects/{id}/cost-sheet` (upload) and
  `GET /v1/projects/{id}/cost-sheet(/info)` (serve/metadata), org-scoped.

## [1.11.0] — 2026-07-10

### Added — AI-assisted data entry
- **AI Import** (Admin → 🪄 AI Import) — upload a brochure/price-list PDF and
  Gemini extracts the structured data (type, land parcel, green area, status,
  possession, towers, configurations with pricing, payment plan) into an
  **editable preview**. Prices are highlighted for review. Nothing is saved until
  the admin confirms; on save it writes to the project's SQL tables.
- Endpoints: `POST /v1/admin/extract` (PDF → draft, nothing saved) and
  `POST /v1/admin/projects/{id}/apply` (reviewed draft → SQL). Org-scoped,
  audited; the AI never invents figures (unknown values come back blank).

## [1.10.0] — 2026-07-10

### Added — Richer project details
- New project fields: **Type** (Residential/Commercial/Industrial), **Land parcel**,
  **Green/open area**, and a **Delivered** status option.
- **Per-tower details** — a new towers table; each tower has a name, floors,
  height and units/floor. Managed under Admin → Manage Data → Towers.
- **Project Details** editor (Manage Data) to edit these attributes on existing
  projects; the New Project form includes them too.
- Project page now shows an **Overview** section (type, land, green area, total
  towers) and a **Towers** table.
- Query engine understands project overview questions ("land parcel", "how many
  towers", "project type") and answers from SQL.

## [1.9.1] — 2026-07-10

### Fixed
- **"View Brochure" always shows the newest** — the latest brochure is now chosen
  by most-recent upload time, and a Replace refreshes that timestamp. Previously,
  ordering by version could surface an older (higher-version) document over a
  newer separate upload.

## [1.9.0] — 2026-07-10

### Added
- **View Brochure** — the project detail page now shows a "View Brochure" button
  when a project has an uploaded brochure. It opens the latest brochure PDF in an
  inline viewer (modal iframe) with a Download option. Streamed via
  `GET /v1/projects/{id}/brochure` (+ `/brochure/info`), org-scoped so a tenant
  can only view its own project's brochure (cross-tenant access → 404). The PDF
  is fetched with the auth token as a blob, so the file stays access-controlled.

## [1.8.0] — 2026-07-10

### Changed — Branding: PropX Estate
- App rebranded to **PropX Estate** with a gold SVG wordmark + "PX" monogram
  (logo, sidebar, login, favicon, browser title).
- Product tagline is now **Knowledge Guru**; the main heading reads
  "Ask the Knowledge Guru".
- Replaced all emoji nav/action icons with professional line SVG icons.

## [1.7.0] — 2026-07-10

### Added
- **Response caching** — repeated expensive queries are served from a per-org
  Redis cache (≈17× faster, no LLM cost). A "⚡ cached" chip marks cached
  answers; cache hits don't consume quota. Freshness via a 10-min TTL plus a
  per-org cache version that is bumped on any data change (price/document/
  project edits). Follow-ups (context-dependent) are never cached.
- **Company-wide quota** — a plan's `daily_llm_quota` now caps the whole
  organization's daily AI queries (in addition to per-employee tier limits).
- **Usage dashboard** — Analytics now shows AI usage today per employee
  (used/limit bar, tier, over-limit in red) and the company total vs plan quota.

## [1.6.0] — 2026-07-10

### Added — Employee tiers + daily query quota (Phase 2)
- **Per-employee tiers** — org-admins assign each employee a **basic** or
  **advanced** tier from the Users panel (create-form field + per-row dropdown).
- **Per-tier daily limits** — org-admins set the daily AI-query limit for each
  tier for their company (`GET/PUT /v1/admin/users/tier-limits`).
- **Quota enforcement** — only expensive queries (LLM/RAG) count against the
  limit; cheap SQL look-ups (price, inventory…) are always free. When an
  employee hits their daily cap they get a clear "daily limit reached" message
  and a chip; counters live in Redis (24h TTL) and fail open if Redis is down.
- Super-admins are unlimited.

## [1.5.0] — 2026-07-10

### Added — Super-admin console (Phase 3)
- **Platform console** (super-admin only, new "🏛️ Platform" nav) to run the SaaS:
  - **Organizations** — list all tenants with plan, employees (used/max), queries
    today (used/quota), and active status; change a company's plan from a dropdown;
    suspend/reactivate; create a new company together with its first admin.
  - **Plans** — create plans and inline-edit their limits (max employees, daily
    query quota, monthly price).
- `is_super_admin` is now returned on login so the UI shows the right console.
- `require_super_admin` guard on all `/v1/superadmin/*` endpoints (org-admins get 403).

## [1.4.0] — 2026-07-10

### Added — Multi-tenant SaaS foundation
- **Organizations (tenants) + Plans** — every user and project belongs to an
  organization; plans (Basic/Advanced/Enterprise) are data-driven and carry
  limits (`max_employees`, `daily_llm_quota`).
- **Tenant isolation** — all reads (projects, query engine, RAG, knowledge,
  analytics, documents) are scoped to the caller's organization. One tenant can
  never see another's data; cross-tenant access returns 404.
- **Super-admin** role (the SaaS owner) — no organization, can operate across all
  tenants; seeded as `owner@engine.local`.
- **Employee cap enforcement** — creating a user beyond the plan's
  `max_employees` is rejected with an upgrade prompt.
- Query log now records `organization_id` for per-tenant usage analytics.

### Changed
- LLM project-disambiguation now only fires on a fuzzy near-miss, saving an API
  call (and avoiding latency) on clearly-unrelated queries.
- Existing data migrates into a default "Chaahat Homes" organization on upgrade.

## [1.3.0] — 2026-07-10

### Added
- **Real Gemini embeddings for RAG** — `gemini-embedding-001` at 768-dim (via
  `output_dimensionality`) so brochure search is truly semantic (e.g. "walk my
  dog" finds the pet zone). Embedding model is configurable and merged through
  runtime config.
- **Re-index all** — `POST /v1/admin/knowledge/reindex-all` re-embeds every
  document with the current provider (run after switching embeddings).
- **Model dropdowns in AI Settings** — LLM and embedding model pickers populated
  live from your Gemini account (`GET /v1/admin/settings/models`), with a
  "Custom…" escape hatch.

### Fixed
- **Expired-token handling** — an authenticated request that returns 401 now
  clears the session and redirects to login instead of hanging on "Loading…".

## [1.2.0] — 2026-07-10

### Added
- **Real Gemini support hardened** — the engine now works with current Gemini
  "thinking" models. Response parsing safely handles empty visible parts
  (falls back to candidate parts), and the default model is `gemini-flash-latest`
  (the old `gemini-1.5-flash` is retired).

### Changed
- **Smarter grounding prompt** — the LLM now presents whatever facts the context
  contains and marks only the specific missing detail as unavailable, instead of
  refusing the whole answer. It still never invents figures (Constitution §8).
- Connection-test token budget raised so thinking models can respond.

## [1.1.1] — 2026-07-10

### Fixed
- **Wrong-project answers via session memory** — asking about an unknown project
  (e.g. "gic price") no longer silently returns the *previous* project's data.
  The engine now says "Information not available — did you mean: …?" and lists
  the known projects (Constitution §8, no guessing).
- **Substring over-matching** — a "Palm Greens" query no longer also matches
  "Green Valley" ("green" inside "greens"). Project linking now uses whole-word
  matching.

### Added
- **Typo-tolerant project matching** — layered linking (exact → fuzzy → LLM).
  Misspellings like "gold hils" resolve to "Golf Hills"; the answer shows a
  "Showing results for Golf Hills" note and a "corrected spelling" chip. Fuzzy
  works offline; LLM disambiguation kicks in only with a real provider.
- Regression tests for entity linking (`tests/test_intent.py`).

## [1.1.0] — 2026-07-10

### Added
- **Price updates** — update an existing configuration's price from the admin
  panel. The old price is kept in history (versioned `effective_from`/`effective_to`)
  and the new one becomes current immediately (`PUT /v1/admin/configurations/{id}/price`).
- **Inventory updates** — change available/total units for a configuration
  (`PUT /v1/admin/configurations/{id}/inventory`).
- **Config editor UI** — Admin → Manage Data → "Update Price / Stock" lists every
  configuration with its current price and stock for inline editing.
- **Brochure replace** — upload a new PDF for an existing document; the old
  brochure's chunks are deactivated so RAG only serves the latest
  (`POST /v1/admin/knowledge/documents/{id}/replace`). Added "Replace" action to
  the Documents tab.
- `GET /v1/admin/projects/{id}/configurations` — list configs with current price + inventory.

## [1.0.0] — 2026-07-10

First complete version — the full hybrid engine, web client, and admin suite.

### Added
- **Hybrid query pipeline** — Intent → Database → Calculation → RAG → LLM → Renderer
  (Golden Rule: deterministic sources answer first; LLM only reasons over facts).
- **SQL-first schema** — builders, projects, configurations, versioned prices,
  payment plans, inventory, offers, documents, users, audit log.
- **RAG subsystem** — PDF ingestion → chunk → embed → pgvector; retrieval with
  page-level citations; provider-aware similarity threshold.
- **Deterministic calculation engine** — total cost, payment schedule, EMI, ROI,
  GST, PLC, rental yield, stamp duty.
- **LLM provider abstraction** — swap Gemini/Claude/OpenAI/Ollama by config only;
  runs fully offline in `mock` mode with no key.
- **Session memory** — follow-up questions keep project context.
- **Structured responses** — cards, tables, timelines, checklists + source
  citations (Project, Source, Page, Last Updated, Confidence).
- **AI Settings** — admins set provider/model/key from the UI (key stays server-side).
- **Smart features** — side-by-side comparison, budget/config recommendations,
  follow-up suggestion chips, voice input.
- **Admin & data** — project/config/payment-plan CRUD, CSV bulk import, users,
  builders, configurable document types, audit trail.
- **Monitoring** — analytics dashboard (queries, miss rate, latency, top intents),
  Knowledge/RAG health (chunks, embeddings, coverage), System Health page.
- **Web client** — React + Vite sales UI; minimal, fast, card/table based.
- **Deployment** — Docker Compose (FastAPI + PostgreSQL/pgvector + Redis).

[Unreleased]: https://github.com/OWNER/REPO/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/OWNER/REPO/releases/tag/v1.0.0
