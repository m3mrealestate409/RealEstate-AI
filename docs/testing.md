# Testing

The backend uses **pytest** (`pytest`, `pytest-asyncio`). Tests live in
`backend/tests/` and are configured by `backend/pytest.ini`:

```ini
[pytest]
testpaths = tests
addopts = -q
```

## Test philosophy

- **Pure, fast unit tests.** The shipped suite covers deterministic helpers that
  run **without a database or network** — the parts most prone to silent
  regressions (entity linking, calculation, embeddings).
- **Mock mode enables end-to-end runs without keys.** With `LLM_PROVIDER=mock`
  and `EMBEDDING_PROVIDER=mock`, the whole engine runs deterministically, so
  higher-level tests and manual QA need no external API.

## Current suite

| File | Covers |
|---|---|
| `tests/test_intent.py` | Intent detection & project entity-linking (the "gic"/"Green Valley" fuzzy-match regressions). |
| `tests/test_calculation.py` | Price/plan calculations. |
| `tests/test_embeddings.py` | The mock embedding provider (determinism, dimensions). |

## Running

```bash
# inside the API container (has all deps)
docker compose exec api sh -c "cd /app && python -m pytest -q"

# or locally, from backend/, in a venv with requirements installed
cd backend && python -m pytest -q
```

Run a single file or test:

```bash
python -m pytest tests/test_intent.py -q
python -m pytest tests/test_intent.py::test_typo_matches_correct_project -q
```

## Conventions

- One test module per subject; test names describe the behavior/regression they
  lock in (e.g. `test_typo_matches_correct_project`).
- Prefer testing **pure functions** directly so tests stay database-free and fast.
- For code that touches Redis or an external provider, inject a fake/mock rather
  than requiring live infrastructure (fail-open helpers make this easy).
- A test that reproduces a bug should be committed *with* the fix and named after
  the bug.

## What is not yet covered (see [roadmap.md](roadmap.md))

- API-level integration tests via `TestClient` (endpoint auth, tenant isolation,
  RBAC) are a valuable next layer.
- No coverage threshold is enforced in CI yet.
- Frontend has no automated tests; it is verified manually and via the browser
  preview.

> The separate, unmerged `security-sprint-1` branch adds a dedicated security
> test suite (secret guard, SSRF/DNS-rebind, login lockout, headers, seat-cap
> race). Those tests are not part of `main` and are documented there.
