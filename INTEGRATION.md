# PropX Estate — Integration Guide (API-first)

The engine is **API-first**: every capability is an HTTP endpoint. The web app is
just one consumer — your **CRM, WhatsApp bot, voice agent, or any website** can
call the same API.

## 1. Authentication

Two ways to authenticate:

| Method | Header | Use for |
|--------|--------|---------|
| **API key** (recommended for integrations) | `X-API-Key: px_...` | CRM, WhatsApp, voice, server-to-server. Permanent, revocable. |
| JWT bearer token | `Authorization: Bearer <token>` | The web app / per-user sessions (8h expiry). |

### Get an API key
Admin → **API Keys** → *Create key*. The full key is shown **once** — copy it.
It acts **within your organization only** (tenant-scoped), so it can never see
another company's data. Revoke anytime from the same screen.

## 2. Base URL
```
Local:       http://localhost:8001
Production:  https://api.yourdomain.com
```
Keep this in a config/env var in your CRM so switching is one line.

## 3. The main endpoint — ask a question

`POST /v1/query`

```jsonc
{
  "query": "Golf Hills 3BHK price and payment plan",  // max 1000 chars
  "session_id": "crm-user-42",   // optional; keeps multi-turn context
  "format": "text"               // "blocks" (default) | "text" | "voice"
}
```

**`format` options:**
- `blocks` — rich structured blocks (tables/cards) for building a UI.
- `text` — clean plain-text answer (great for CRM inline / WhatsApp).
- `voice` — short, spoken, no-markdown answer (for a voice/calling agent).

**Response** (key fields):
```jsonc
{
  "answer_text": "...ready-to-use plain text...",   // use this for CRM/WhatsApp/voice
  "content": { "blocks": [ ... ] },                 // structured (for rich UIs)
  "citations": [ ... ],                             // sources (project, page, confidence)
  "confidence": 0.98,
  "handlers_used": ["database"],                    // database | rag | llm | internet
  "unverified": false                               // true = general-knowledge fallback
}
```

### Examples

**cURL**
```bash
curl -X POST https://api.yourdomain.com/v1/query \
  -H "X-API-Key: px_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"query":"why buy golf hills","format":"voice"}'
```

**JavaScript (CRM backend)**
```js
const res = await fetch(`${RAG_API_URL}/v1/query`, {
  method: "POST",
  headers: { "X-API-Key": process.env.RAG_API_KEY, "Content-Type": "application/json" },
  body: JSON.stringify({ query, session_id: `crm-${userId}`, format: "text" }),
});
const { answer_text } = await res.json();
```

## 4. Other useful endpoints (all accept the API key)
- `GET /v1/projects` — list projects (`?q=` to search)
- `GET /v1/projects/{id}/price` — current prices (base + per-plan)
- `GET /v1/projects/{id}/payment-plan`, `/inventory`, `/amenities`, `/towers`, `/location`
- `GET /v1/projects/{id}/brochure` and `/cost-sheets` — PDFs
- `POST /v1/calculate/{type}` — EMI / total-cost / etc.

Full auto-generated reference: **`/docs`** (OpenAPI/Swagger).

## 5. Notes
- **Tenant isolation:** a key only ever sees its own organization's data.
- **Quota:** expensive (LLM/RAG) queries count against the org's daily quota;
  plain SQL look-ups (price, inventory…) are free.
- **CORS:** for browser-side calls from a website, add its origin to
  `CORS_ORIGINS`. Server-to-server calls (recommended) don't need CORS.
- **Security:** treat API keys like passwords — store server-side, never expose
  in frontend code.
