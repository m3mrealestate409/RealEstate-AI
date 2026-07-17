# PropX Estate — Documentation

**PropX Estate** (internal name: *Chaahat Homes AI Knowledge Engine*) is a
multi-tenant SaaS that gives a real-estate company an AI assistant grounded in
its own structured data. Sales staff, a public website chat widget, and a CRM
all ask questions in natural language; the engine answers from the database
first and only uses a large language model (LLM) as a last resort, so prices,
payment plans, inventory and dates are always exact.

- **Version:** 1.0.0
- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 · PostgreSQL 16 + pgvector · Redis
- **Frontend:** React 18 · Vite 6
- **LLM:** provider-agnostic (Gemini by default; also Claude/OpenAI/OpenRouter/Ollama/mock)
- **Deployment:** Docker Compose

---

## What it does

| Capability | Summary |
|---|---|
| **Grounded Q&A** | Answers about a project's price, payment plan, inventory, amenities, possession, RERA, location, offers — from SQL, never invented by the LLM. |
| **Multi-tenant** | Each real-estate company (an *organization*) is fully isolated: its own users, projects, documents, leads and conversations. |
| **Website chat widget** | A one-line `<script>` embed that answers visitors, captures leads, and hands off to a human. |
| **Live Chat + takeover** | Staff watch website conversations in real time and take over from the bot. |
| **CRM integration** | Inbound API (your CRM asks the engine) and an outbound lead webhook (the engine pushes every new lead to your CRM). |
| **Billing** | Plans, subscriptions, hand-recorded payments, printable receipts, plan-change requests. |
| **RAG knowledge** | Upload brochures/PDFs; facts are extracted into the database, and prose is retrieved via vector search for the LLM to summarize. |

---

## Documentation map

| Document | Read it to… |
|---|---|
| [architecture.md](architecture.md) | Understand the components and the hybrid answer pipeline. |
| [rag-pipeline.md](rag-pipeline.md) | Learn exactly how a question becomes an answer (the "Golden Rule"). |
| [data-model.md](data-model.md) | See the database schema and how multi-tenancy is enforced. |
| [api-reference.md](api-reference.md) | Call the REST API — endpoints, auth, examples. |
| [configuration.md](configuration.md) | Every environment variable and what it controls. |
| [deployment.md](deployment.md) | Run it with Docker and harden it for production. |
| [integrations.md](integrations.md) | Embed the widget; connect a CRM, Telegram, or WhatsApp. |
| [admin-guide.md](admin-guide.md) | Day-to-day use: roles, projects, billing, live chat, import/export. |
| [security.md](security.md) | The authentication, authorization and abuse-protection model. |

### Related files in the repository root (not in `/docs`)
- `README.md` — quick-start.
- `PRD.md` — the product "constitution" (the non-negotiable design rules).
- `INTEGRATION.md` — integration notes.
- `CHANGELOG.md` — release history.

---

## Core principle (the "Golden Rule")

> Facts come from deterministic sources (SQL, calculators). The LLM only ever
> reasons over data that has already been retrieved — it never invents prices,
> dates or figures. If nothing is found, the engine says so.

Everything in this documentation follows from that rule. See
[rag-pipeline.md](rag-pipeline.md) for the full pipeline.
