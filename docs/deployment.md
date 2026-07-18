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

## Production deploy on a VPS (e.g. Hostinger)

The production overlay ([`docker-compose.prod.yml`](../docker-compose.prod.yml))
adds a **`web` edge** (Caddy) that serves the built React SPA **and** reverse-proxies
`/v1`, `/static`, `/health` to the API — one origin, automatic HTTPS. The API, DB,
and Redis stay off the public internet; only `web` (80/443) is exposed.

> **Every `yourdomain.com` below is a placeholder — replace it with your real
> domain.** It appears in exactly one place you edit: the `.env` file
> (`SITE_ADDRESS`, `VITE_API_URL`, `CORS_ORIGINS`). Nothing else needs editing.

### Sizing
- **Recommended:** a 2 vCPU / 8 GB VPS (Hostinger **KVM 2**). Handles Postgres +
  pgvector, Redis, the API (4 workers), and the SPA build comfortably.
- **Minimum:** 1 vCPU / 4 GB (KVM 1) — fine for light/demo load; the build is tight.
- Pick the **Ubuntu 24.04 + Docker** template so Docker & Compose are preinstalled.
  Enable the panel's weekly backups.

### Steps

**1. Point the domain at the VPS.** In your DNS, add an `A` record for
`yourdomain.com` → the VPS IP. Wait for it to resolve before step 6 (Caddy needs
it to issue the TLS cert).

**2. Log in and lock the box down.**
```bash
ssh root@YOUR_VPS_IP
adduser deploy && usermod -aG sudo deploy      # a non-root sudo user
# (optional) copy your SSH key to `deploy`, then disable root/password SSH login
ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw enable
```
> Note: Docker-published ports can bypass `ufw`. Here that's fine — only `web`
> publishes (80/443), and DB/Redis/API are bound to `127.0.0.1`. Keep it that way.

**3. Install Docker** *(skip if you used the Docker template).*
```bash
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker deploy
```
Log out/in so the group applies.

**4. Get the code.**
```bash
git clone https://github.com/m3mrealestate409/RealEstate-AI.git
cd RealEstate-AI
```

**5. Configure `.env`.**
```bash
cp .env.production.example .env
# generate strong secrets:
openssl rand -hex 32   # → paste as SECRET_KEY
openssl rand -hex 24   # → paste as POSTGRES_PASSWORD (and into DATABASE_URL)
openssl rand -hex 24   # → paste as REDIS_PASSWORD  (and into REDIS_URL)
nano .env
```
In `.env`, set: `SECRET_KEY`, `POSTGRES_PASSWORD` (+ the same value inside
`DATABASE_URL`), `REDIS_PASSWORD` (+ inside `REDIS_URL`), `GEMINI_API_KEY`,
strong `SEED_ADMIN_PASSWORD` / `SEED_SUPER_ADMIN_PASSWORD` with real emails, and
the three domain fields — **`SITE_ADDRESS=yourdomain.com`**,
**`VITE_API_URL=https://yourdomain.com`**, **`CORS_ORIGINS=https://yourdomain.com`**.

**6. Build & start.**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
Caddy fetches a Let's Encrypt cert automatically on first boot.

**7. Verify & secure the first login.**
```bash
curl -s http://127.0.0.1:8001/health          # API up (loopback)
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f web   # watch cert issuance
```
Open `https://yourdomain.com`, log in with the seeded super-admin, and **change
both seeded passwords** from the UI.

### If the domain changes later
`VITE_API_URL` is baked into the SPA at **build time**, so after editing the
domain in `.env` you must **rebuild the web image**:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build web
```

### Fresh vs. demo data
A brand-new VPS starts with an empty database; the seeder creates only your
admin/super-admin from `SEED_*`. (Your local dev DB has demo orgs/projects — those
do **not** travel to the server. Use the super-admin **Import** feature to load a
real project pack.)

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
- ✅ TLS terminated at the `web` (Caddy) edge with automatic HTTPS; the SPA and
  `widget.js` are served over HTTPS. *Handled by the prod overlay.*
- [ ] Note: Docker-published ports bypass host firewalls (iptables `FORWARD`
  chain) — rely on binding + a cloud security group, not just `ufw`.

### Application hardening
- ✅ API container runs as a non-root user (`appuser`, via `gosu`). *Prod overlay.*
- ✅ `--reload` is off in production (`entrypoint.prod.sh`, multi-worker). *Prod overlay.*
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
