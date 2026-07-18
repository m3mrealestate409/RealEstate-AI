# Configuration Reference

All configuration is environment-driven (`backend/app/config.py`, Pydantic
Settings). Copy `.env.example` to `.env` and fill in values. **No secret is ever
exposed to the frontend** — only `VITE_API_URL` reaches the browser bundle.

## Application

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Set to `production` in prod. Any value other than `development`/`dev`/`test`/`testing`/`local` is treated as production, which turns on strict startup guards. |
| `APP_DEBUG` | `true` | When `true`, CORS allows all origins (dev only). Set `false` in production and use `CORS_ORIGINS`. |
| `SECRET_KEY` | placeholder | JWT signing key. **Must** be a strong 32+ char random value in production — the app refuses to boot otherwise. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | JWT lifetime (8 hours). |
| `CORS_ORIGINS` | empty | Comma-separated allow-list, used only when `APP_DEBUG=false`. e.g. `https://app.yourdomain.com`. |

## Database & cache

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `chaahat` / `chaahat_pass` / `chaahat_engine` | Compose credentials. **Change the password in production.** |
| `DATABASE_URL` | local dsn | SQLAlchemy DSN. Compose overrides the host to `db`. |
| `REDIS_URL` | `redis://localhost:6379/0` | Session memory, quotas, rate limits. Compose overrides the host to `redis`. |

## LLM provider (swap by config only)

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `mock` | `mock` \| `gemini` \| `claude` \| `openai` \| `openrouter` \| `ollama`. `mock` runs the entire engine with **no API key**. |
| `LLM_MODEL` | `gemini-flash-lite-latest` | Model id. flash-lite = "thinking" off → faster + cheaper. |
| `GEMINI_API_KEY` | placeholder | Real Gemini key (free at aistudio.google.com/apikey). |
| `OPENAI_API_KEY` / `CLAUDE_API_KEY` / `OPENROUTER_API_KEY` | empty | For those providers. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama endpoint. |

The active provider/key can also be set at runtime by a super-admin via
`/v1/admin/settings/llm` (stored in the `settings` table); that overlays these
defaults. Keys are never returned to the browser.

## Embeddings (RAG vectors)

| Variable | Default | Description |
|---|---|---|
| `EMBEDDING_PROVIDER` | `mock` | `mock` (deterministic, no key) or `gemini`. |
| `EMBEDDING_MODEL` | `gemini-embedding-001` | Embedding model. |
| `EMBEDDING_DIM` | `768` | **Must** match the pgvector column dimension. |

## RAG tuning

| Variable | Default | Description |
|---|---|---|
| `RAG_TOP_K` | `5` | Chunks retrieved per query. |
| `RAG_SIMILARITY_THRESHOLD` | `0.35` | Minimum cosine similarity to include a chunk. |

## Seed accounts (first boot)

| Variable | Default | Description |
|---|---|---|
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | `admin@chaahat.local` / `admin123` | Default org admin. |
| `SEED_SUPER_ADMIN_EMAIL` / `SEED_SUPER_ADMIN_PASSWORD` | `owner@engine.local` / `owner123` | Platform owner. |

> **Production guard:** when `APP_ENV=production`, the seeder refuses to run with
> the demo passwords (`admin123` / `owner123`). Set strong values.

## Frontend

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8001` | Backend base URL baked into the SPA. The **only** var that reaches the browser. |

## Startup behavior

- `init_db.py` creates tables and runs idempotent `ADD COLUMN IF NOT EXISTS`
  migrations. Column-adding migrations run **only at container start** — restart
  the API after a schema change.
- `seed.py` seeds plans, the default organization, and the admin/super-admin.
- In production, boot fails fast on a weak `SECRET_KEY` or default seed passwords.

See [deployment.md](deployment.md) for the full production checklist.
