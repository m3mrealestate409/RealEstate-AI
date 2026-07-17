# Troubleshooting

Practical fixes for the issues that come up most, grouped by symptom. See also
[operations.md](operations.md) for monitoring and recovery.

## Startup

**API container exits immediately in production.**
- `SECRET_KEY must be a strong … value in production` → set a strong `SECRET_KEY`
  (`python -c "import secrets; print(secrets.token_urlsafe(48))"`). The app
  refuses to boot on a weak/default key when `APP_ENV=production`.
- Seeder refuses default passwords → set non-default `SEED_ADMIN_PASSWORD` /
  `SEED_SUPER_ADMIN_PASSWORD`.
- DB not ready → the API waits on the `db` health check; check `docker compose
  logs db`.

**A new column/table is missing after a schema change.**
- Migrations (`ADD COLUMN IF NOT EXISTS`) run **only at container start**.
  `docker compose restart api`. Code-only changes hot-reload; schema changes do not.

## Answers

**Assistant says "Information not available in the current knowledge base."**
- The org has no data for that project yet. Add projects/prices or upload a
  brochure (see [admin-guide.md](admin-guide.md)).
- You're in **mock mode** (`LLM_PROVIDER=mock`) — expected for prose questions;
  exact facts still work. Set a real `GEMINI_API_KEY` and `LLM_PROVIDER=gemini`
  for composed answers.

**Answers are too long / wrong tone.**
- Tune the **assistant persona** (Admin → Assistant → Identity & Persona). Persona
  controls tone only; it never changes facts.

**A price/figure looks wrong.**
- Facts come from the database, not the LLM — fix the value in Projects & Data.
  If it's still wrong, it's a data-entry issue, not a model hallucination.

## Widget

**Widget doesn't appear on the site.**
- Confirm the `<script>` is before `</body>` and `data-api-url` points at the
  reachable backend (public domain in prod, not `host.docker.internal`).
- Check the browser console/network tab for a blocked request (CORS/mixed
  content). Serve the widget and API over HTTPS in production.

**Widget loads but calls fail (401/403).**
- The `data-api-key` must be a **widget-scope** key. A revoked or wrong-scope key
  returns 401/403. Create a fresh Website / Widget-only key.

**CORS errors in the browser.**
- In production set `APP_DEBUG=false` and `CORS_ORIGINS=https://your-frontend`.
  With `APP_DEBUG=true` all origins are allowed (dev only).

## CRM / webhooks

**Leads aren't reaching the CRM.**
- Is the **Lead Webhook** URL set (Admin → Integrations → Lead Webhook)? An empty
  URL means no push.
- URL must start with `http://` or `https://`.
- Local testing: the engine runs inside Docker, so a local CRM is reachable at
  `http://host.docker.internal:<port>/…`, **not** `127.0.0.1`.
- A `4xx` from your CRM is treated as a permanent rejection (not retried) — check
  your endpoint accepts the JSON payload and the secret header.
- Nothing lost: pull `GET /v1/admin/leads` to catch up any missed leads.

**Telegram/WhatsApp test fails.**
- Telegram: the bot must have been messaged once and added to the target chat;
  verify the chat id (groups start `-100`).
- WhatsApp Cloud API: check the `Authorization: Bearer` header and Meta body
  shape. See [integrations.md](integrations.md).

## Infrastructure

**Rate limits/quotas not being enforced.**
- Redis is likely unreachable. The limiter **fails open** by design (logs
  `Redis unavailable … limits not enforced`). Fix `REDIS_URL`/the `redis`
  container; data is never affected.

**Reading Docker logs shows old/rotated output.**
- Docker rotates JSON logs; a large `--tail`/`--since` may read a rotated segment
  and appear to "stop" at an old timestamp. Use a small `--tail` for the newest
  segment, or query the app's own logs/metrics.

## Environment-specific (Windows / dev)

- Console scripts printing `₹`/`→`/`✓` can fail under cp1252 — set
  `PYTHONIOENCODING=utf-8`.
- Inside containers use `host.docker.internal` to reach host services, never
  `127.0.0.1`.

## Still stuck?
- Check **Admin → System → System Health** (DB, Redis, pgvector, LLM status).
- Check `docker compose logs api` (and `db` / `redis`).
- Confirm `/health` returns 200.
