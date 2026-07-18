# Admin & User Guide

Day-to-day use of the app, organized by the Admin console's categories.

## Roles — who can do what

| Role | Can | Created by |
|---|---|---|
| **Super-admin** (platform owner) | Manage all tenants, plans/pricing, record payments, seed projects. Has **no** organization. | Seeded on first boot. |
| **Admin** (org owner) | Everything within their company: projects, team, billing, integrations, live chat, settings. | Comes **with** the organization (super-admin creates the org + its one admin). |
| **Manager** | Ask questions, plus Analytics and Knowledge. | An org admin. |
| **Sales** | Ask questions and see projects. | An org admin. |

Two independent settings per person:
- **Role** = what they can *see/do*.
- **Tier** (`basic` / `advanced`) = how many *AI questions per day* they get.
  A sales person can be Advanced; a manager can be Basic. Per-tier daily limits
  are set in **Admin → Team**.

> An org admin can only create **managers** and **sales**. Admin accounts come
> with the organization itself — contact the platform owner to add another admin.

## Adding your projects (knowledge)

The assistant answers from your data, so start by loading projects:

1. **Admin → Projects & Data → New Project** — create a project shell.
2. Add facts: configurations (unit types + areas), prices, payment plans,
   towers, amenities, location points, inventory.
3. **Upload brochures** in **Admin → Knowledge** — the AI extracts structured
   facts and indexes the prose for retrieval.
4. Or **AI Import** — extract a project's data straight from a PDF, review, apply.

### Bulk import / export (Projects & Data → Import / Export)
- **Export pack (JSON)** — a project's *whole* knowledge tree (configs, prices,
  plans, towers, amenities). Use it as a backup, to edit offline, or to hand to
  us to load into another company.
- **Export CSV** — the flat project list for Excel (names only — no prices/plans).
- **Import a pack (JSON)** — loads projects *with* their prices/plans/amenities.
  Projects you already have (same slug) are **skipped** — an import never
  overwrites live prices.
- **Import a CSV** — creates project *shells* only; you still add prices/plans.

Brochures/documents are never included in exports — they stay with the company
that owns them.

## The assistant's identity (Admin → Assistant)

- **Identity & Persona** — name, photo, personality **and the chat greeting**,
  with a live preview of the widget. Applies everywhere (widget, CRM, app). It
  changes look and tone only; prices and facts always come from your data.
- **Notifications** — get alerted when a new website visitor starts chatting
  (Telegram or webhook). See [integrations.md](integrations.md).

## Live Chat & human takeover

- **Live Chat** shows website conversations in real time. A green dot means the
  visitor is online; an offline visitor's takeover control is disabled.
- Click **Take over** to switch a chat from AI to human; the visitor sees your
  messages, and the bot pauses. **Release** hands it back to the AI.
- Access: all admins, plus any employee granted Live Chat in **Admin → Team**.

## Leads

- Leads are captured from the widget's callback form or when a visitor types a
  phone number in chat, tagged with the project they asked about.
- **Admin → Growth → Leads** lists them; update status or delete.
- Every lead is also pushed to your CRM if a Lead Webhook is configured, and can
  be re-synced via `GET /v1/admin/leads`. See [integrations.md](integrations.md).

## Billing (Admin → 💳 Billing)

- **Plan & Usage** — your plan, status, expiry, and usage vs caps.
- **Payments** — every payment received, with a printable **receipt** per row
  and a **CSV** download. (Receipts are payment receipts, not GST tax invoices.)
- **Pricing** — plan cards; **Request this plan** to ask us to change your plan
  (it charges nothing — it raises a request the platform owner actions).

A banner appears across Admin if your subscription lapses. When a subscription is
suspended, **only AI answers pause** — logins, data, price look-ups and leads all
keep working, and the website widget quietly falls back to database answers.

## System (Admin → ⚙️ System)

- **System Health** — live status of PostgreSQL, Redis, pgvector and the LLM.
- **Audit Log** — a record of changes (who did what).
- **AI Settings** (super-admin) — choose the LLM provider and paste the key.

## Platform console (super-admin only)

- **Organizations** — every tenant as a card: billing status, usage meters,
  plan, paid-till, pending plan requests. Record a payment (date + amount +
  method + reference), suspend, or start a trial. Seed a new tenant with a
  starter set of projects copied from another company.
- **Plans** — set each plan's price, employee cap and daily AI-query quota;
  hide a plan from the pricing page.
- **Alerts** — the platform owner's own notification channel.

The 🔔 bell in the sidebar shows pending plan-change requests at a glance.
