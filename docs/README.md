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

**Understand the system**
| Document | Read it to… |
|---|---|
| [architecture.md](architecture.md) | Understand the components and the hybrid answer pipeline (diagrams). |
| [rag-pipeline.md](rag-pipeline.md) | Learn exactly how a question becomes an answer (the "Golden Rule"). |
| [workflows.md](workflows.md) | See the cross-component flows (takeover, subscription lifecycle, billing) as diagrams. |
| [data-model.md](data-model.md) | The database schema, ER diagram, and how multi-tenancy is enforced. |

**Build & integrate**
| Document | Read it to… |
|---|---|
| [api-reference.md](api-reference.md) | Call the REST API — endpoints, auth, examples. |
| [frontend.md](frontend.md) | The React SPA — structure, routing, rendering, build. |
| [integrations.md](integrations.md) | Embed the widget; connect a CRM, Telegram, or WhatsApp. |
| [development.md](development.md) | Coding standards, migrations, extension points, recipes. |
| [testing.md](testing.md) | The test suite, how to run it, conventions. |

**Operate**
| Document | Read it to… |
|---|---|
| [configuration.md](configuration.md) | Every environment variable and what it controls. |
| [deployment.md](deployment.md) | Run it with Docker and harden it for production. |
| [operations.md](operations.md) | Monitoring, backup, disaster recovery, scaling, performance. |
| [troubleshooting.md](troubleshooting.md) | Fix the issues that actually come up. |
| [security.md](security.md) | The authentication, authorization and abuse-protection model. |

**Plan & reference**
| Document | Read it to… |
|---|---|
| [roadmap.md](roadmap.md) | Technical debt, in-progress hardening, and the product roadmap. |
| [glossary.md](glossary.md) | Definitions of the domain terms used throughout. |
| [DOCUMENTATION_GAP_REPORT.md](DOCUMENTATION_GAP_REPORT.md) | The documentation audit: completeness score and gaps. |

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
