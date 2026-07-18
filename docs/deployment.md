# Deployment & Operations

The stack runs on Docker Compose: an API container, PostgreSQL (pgvector), and
Redis. The React SPA is built with Vite and served as static assets.

## Quick start (local / development)

```bash
cp .env.example .env          # defaults run in FULL MOCK mode — no API keys needed
docker compose up -d          # starts db, redis, api
# API:      http://localhost:8001        (OpenAPI at /docs)
# Frontend: cd frontend && npm install && npm run dev   → http://localhost:5173
```

On first boot the API creates tables (`init_db`) and seeds plans, the default
organization, and the admin/super-admin (`seed`). Default logins:

- Org admin: `admin@chaahat.local` / `admin123`
- Super-admin: `owner@engine.local` / `owner123`

> **Mock mode:** with `LLM_PROVIDER=mock` and `EMBEDDING_PROVIDER=mock` the whole
> engine works without any external API key — useful for evaluation and CI.

## Ports (as shipped)

| Service | Container | Host |
|---|---|---|
| API | 8000 | 8001 |
| PostgreSQL | 5432 | 5433 |
| Redis | 6379 | 6380 |

Services reach each other by name over the compose network (`db`, `redis`), so
the published host ports exist only for local tooling.

## Operational notes

- **Migrations run at container start.** After changing a model/schema, restart
  the API (`docker compose restart api`) so `init_db`'s `ADD COLUMN IF NOT EXISTS`
  steps run. Code-only changes hot-reload.
- **Redis is fail-open.** If Redis is down, rate limits and quotas are not
  enforced (the app keeps serving); data is never at risk.
- **Networking inside Docker:** containers reach the host via
  `host.docker.internal`, not `127.0.0.1`. This matters for a local CRM webhook.
- **Health checks:** `GET /health` (liveness); `GET /v1/admin/system/…` reports
  DB, Redis, pgvector and LLM status for admins.
- **Backups:** the `db_data` volume is the system of record. Back it up
  regularly; `uploads` holds brochures/avatars.

## Production checklist

The shipped compose file is convenient for local development. Before exposing the
system to the internet, apply the following. (Items marked ✅ are already enforced
by the application at boot.)

### Secrets & environment
- [ ] `APP_ENV=production`, `APP_DEBUG=false`.
- ✅ `SECRET_KEY` — a strong 32+ char random value. *The app refuses to boot in
  production with a weak/default key.*
- ✅ Seed passwords — non-default. *The seeder refuses the demo passwords in
  production.*
- [ ] `CORS_ORIGINS` set to your exact frontend origin(s).
- [ ] `POSTGRES_PASSWORD` — a strong, unique value (not `chaahat_pass`).

### Network exposure
- [ ] **Do not publish PostgreSQL or Redis to public interfaces.** Bind them to
  loopback (`127.0.0.1:5433:5432`, `127.0.0.1:6380:6379`) or drop the host port
  mappings entirely — services already talk over the compose network.
- [ ] Put **Redis behind a password** (`requirepass`) and reflect it in
  `REDIS_URL`.
- [ ] Terminate TLS at a reverse proxy (nginx/Caddy/cloud LB) in front of the API;
  serve the SPA and `widget.js` over HTTPS.
- [ ] Note: Docker-published ports bypass host firewalls (iptables `FORWARD`
  chain) — rely on binding + a cloud security group, not just `ufw`.

### Application hardening
- [ ] Run the API container as a non-root user.
- [ ] Disable `--reload` in production (dev convenience only).
- [ ] Consider disabling `/docs` publicly if you don't want the API surface listed.
- [ ] Front the LLM keys server-side only (they already never reach the browser).

### Widget & keys
- [ ] Website embeds use a **widget-scope** API key (safe to appear in page
  source; it can only run the widget's four endpoints). Never embed a `full` key.

For the reasoning behind each item and the threat it addresses, see
[security.md](security.md).

## Upgrades

1. Pull the new code.
2. `docker compose build api && docker compose up -d` (this reruns `init_db` +
   `seed`, both idempotent).
3. Verify `/health` and the admin **System Health** page.
