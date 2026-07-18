# Key Workflows

Sequence and state diagrams for the flows that span multiple components. For the
answer pipeline see [rag-pipeline.md](rag-pipeline.md); for auth flows see
[security.md](security.md); for the lead → CRM push see
[integrations.md](integrations.md).

## Human takeover (Live Chat)

```mermaid
sequenceDiagram
    autonumber
    participant V as Visitor (widget)
    participant API as Engine
    participant A as Agent console (SPA)

    V->>API: chats (AI mode)
    API-->>A: session appears in /v1/admin/live/sessions
    A->>API: POST .../{id}/takeover
    API->>API: session.mode = human
    Note over V,API: bot stops answering
    V->>API: message
    API-->>A: shown in transcript (poll)
    A->>API: POST .../{id}/message (reply)
    V->>API: GET /v1/widget/poll → agent reply + "human" mode
    A->>API: POST .../{id}/release
    API->>API: session.mode = ai (bot resumes)
```

## Subscription lifecycle (state machine)

Effective status is derived from dates at read time — no cron job. A lapse opens
a grace window before AI answers pause; data is never withheld.

```mermaid
stateDiagram-v2
    [*] --> trialing: org created
    trialing --> active: payment recorded (paid_till set)
    trialing --> past_due: trial ends (within grace)
    active --> past_due: current_period_end passes (within grace)
    past_due --> active: payment recorded
    past_due --> suspended: grace window expires
    suspended --> active: payment recorded
    active --> cancelled: cancel
    suspended --> cancelled: cancel
    cancelled --> active: reactivate + pay

    note right of suspended
        AI answers pause.
        Logins, data, SQL look-ups,
        leads keep working.
    end note
```

## Record a payment (super-admin)

```mermaid
sequenceDiagram
    autonumber
    participant O as Platform owner
    participant API as Engine
    participant DB as PostgreSQL

    O->>API: PUT /superadmin/organizations/{id}/subscription<br/>(paid_till, amount, method, reference)
    API->>DB: write immutable payments row (snapshot plan name)
    API->>DB: subscription.status = active, current_period_end = paid_till
    API-->>O: receipt_no (e.g. PX-2026-00002)
    Note over O,API: tenant admin can later download the receipt / CSV
```

## Plan-change request (tenant → owner)

```mermaid
sequenceDiagram
    autonumber
    participant T as Tenant admin
    participant API as Engine
    participant O as Platform owner

    T->>API: POST /v1/billing/upgrade-request (plan_id)
    API->>API: subscription.requested_plan_id set (charges nothing)
    API-->>O: background ping (Telegram/webhook) + bell badge
    O->>API: PUT .../subscription (plan_id) — action it
    API->>API: plan changed, request cleared
```

## Project import / export

```mermaid
flowchart LR
    subgraph Source org
        P[Projects + configs + prices +<br/>plans + towers + amenities]
    end
    P -->|export pack| J[(projects.json<br/>whole tree)]
    P -->|export csv| C[(projects.csv<br/>names only)]
    J -->|import pack| T[Target org<br/>knowledge loaded]
    C -->|import csv| S[Target org<br/>project shells only]
    P -.->|super-admin seed-projects<br/>same pack code| T

    note1[/"same slug → skipped, never overwrites live prices"/]
    T -.- note1
```

Documents/brochures are never included — they stay with the org that owns them.
See [admin-guide.md](admin-guide.md#bulk-import--export-projects--data--import--export).
