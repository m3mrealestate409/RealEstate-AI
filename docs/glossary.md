# Glossary

Terms used across the documentation and the codebase.

| Term | Meaning |
|---|---|
| **Organization / tenant** | A real-estate company. The unit of isolation — its users, projects, documents, leads and conversations are private to it (`organization_id`). |
| **Super-admin / platform owner** | The operator of the SaaS. Has **no** organization; manages all tenants, plans and payments via `/v1/superadmin/*`. |
| **Admin** | The owner-user of one organization. Full control within their company. |
| **Manager / Sales** | Staff roles. Sales asks questions and sees projects; Manager adds Analytics and Knowledge. |
| **Tier** | A user's daily AI-query allowance (`basic` / `advanced`) — independent of role. |
| **Plan** | A subscription tier for the whole org (Basic/Advanced/Enterprise): employee cap, daily LLM quota, price. |
| **Subscription** | Whether an org has actually *paid* for its plan (status + dates). Distinct from the plan itself. |
| **Effective status** | The subscription's real state (`trialing`/`active`/`past_due`/`suspended`/`cancelled`) derived from dates at read time — no cron. |
| **Entitlements** | The live limits an org may use right now, computed from plan + subscription (`services/billing.py`). |
| **Payment** | An immutable record of money received (amount, method, reference, service period). Powers receipts. |
| **API key** | An integration credential (`X-API-Key`). Has a **channel** and a **scope**. |
| **Channel** | What a key is plugged into: `website` (public widget — raises alerts, in Live Chat) or `internal` (CRM/bot — no alerts, higher limits). |
| **Scope** | What a key may do: `widget` (four public widget calls only), `read_only` (ask + read), `full` (acts as its admin). |
| **Widget** | The embeddable `widget.js` chat added to a builder's website with one `<script>` tag. |
| **Session id** | Identifies a widget conversation for per-session memory and polling. |
| **Live Chat / takeover** | The agent console where staff watch website chats and take over from the AI. |
| **Lead** | A captured prospect (from the callback form or a phone number typed in chat). |
| **Lead webhook** | Outbound: the engine POSTs every new lead to the org's CRM URL. |
| **RAG** | Retrieval-Augmented Generation — vector search over document chunks feeds the LLM. |
| **RAG chunk** | A piece of an uploaded document, embedded into a pgvector column for similarity search. |
| **Block** | A structured answer element (price table, config card, timeline) the SPA renders precisely. |
| **Persona** | The org-set identity/tone of the assistant (name, photo, personality). Affects tone only, never facts. |
| **Pack** | A project's whole knowledge tree exported/imported as one JSON file (configs, prices, plans, amenities…). |
| **The Golden Rule** | Facts come from SQL; the LLM never invents them. See [rag-pipeline.md](rag-pipeline.md). |
| **Mock mode** | `LLM_PROVIDER=mock` / `EMBEDDING_PROVIDER=mock` — the engine runs deterministically with no external API key. |
| **Fail-open / fail-closed** | Rate limits fail *open* (an outage never blocks users); security checks fail *closed*. |
| **Grace window** | The period after a subscription lapses during which everything still works before AI answers pause. |
