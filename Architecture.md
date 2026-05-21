# Architecture

UnifiedIQ is a single-process conversational-BI application: a FastAPI
backend that talks to a Databricks SQL warehouse and the Databricks
Foundation Model API, fronted by a Next.js static SPA that the same backend
serves. The browser talks only to `/api/*` on the same origin — there is
no separate BFF or Node server.

This document describes the runtime topology, the layout of the codebase,
and the cross-cutting concerns (auth, LLM, streaming, persistence, eval,
CI). For feature-level walkthroughs see
[ConversationalBI.md](ConversationalBI.md) and
[Dashboard.md](Dashboard.md).

The system context diagram below is a hand-authored SVG (the three-column
"user devices / application layer / external services" style). All the
technical-flow diagrams further down use [Mermaid](https://mermaid.js.org/).
Both render natively on GitHub and inside VS Code's preview.

## 1. System context

The browser is the only client; identity is terminated by the Databricks
Apps platform; the FastAPI process is the only thing that talks to the
warehouse and the foundation models.

![UnifiedIQ system architecture](assets/architecture.svg)

Two deployment shapes are supported, both built from the same source:

- **Databricks App (production)** — the diagram above. One Python process
  serves both `/api/*` and the SPA from `src/UnifiedIQ-api/static/`.
- **Local two-tier (Docker Compose)** — Next.js dev server on `:3000`,
  FastAPI on `:5000`, optional Postgres on `:5432`. Auth via
  `AUTH_BYPASS=true` or Okta OIDC. Same Python services and SPA build; only
  the hosting boundary differs.

## 2. Backend

Stack: Python 3.12, FastAPI + Uvicorn, Pydantic v2, `openai` (pointed at
Databricks FM API), `instructor` for structured outputs (MD_JSON mode),
`sqlglot` (dialect `databricks`) for SQL validation,
`databricks-sql-connector` for warehouse I/O, `httpx`, `pyjwt[crypto]` for
OIDC.

### Layers

```mermaid
flowchart TB
    subgraph Routers["FastAPI routers"]
      direction LR
      RH["health.py<br/>/api/health /api/me"]
      RC["chat.py<br/>/api/chat<br/>/api/chat/stream (SSE)"]
      RVf["verify.py<br/>/api/chat/verify"]
      RA["alerts.py<br/>/api/alerts<br/>/api/notifications"]
      RV["views.py<br/>/api/views (CRUD + PATCH + /run)"]
      RM["memory.py<br/>/api/memory"]
      RI["integrations.py<br/>/api/integrations"]
    end

    subgraph Services
      direction LR
      SLLM["LLMService<br/>(instructor MD_JSON)"]
      SWH["WarehouseService<br/>(DatabricksWarehouse)"]
      SSchema["SchemaService<br/>(Memory · Tier 1)"]
      SUM["UserMemoryService<br/>(Memory · Tier 4)"]
      SVer["VerifierService<br/>(self-audit + LLM judge)"]
      SAlerts["AlertService<br/>+ AlertScheduler"]
      SViews["ViewsService"]
      SAuth["UserAuth / ServiceAuth"]
      SReg["IntegrationRegistry"]
      SSess["SessionStore<br/>+ async-queue worker"]
      STel["TelemetryLogger<br/>+ async-queue worker"]
      SCache["CacheService<br/>(TTLCache)"]
    end

    subgraph Integrations
      direction LR
      ISlack["SlackIntegration"]
      IEmail["EmailIntegration (SMTP)"]
      IInApp["InAppIntegration<br/>(ring buffer)"]
    end

    Models["Pydantic models<br/>(domain / requests / responses)"]
    Prompts["Prompts<br/>(chat_system, alert_system,<br/>verifier_system, judge_system)"]
    Errors["AppError<br/>+ stable codes"]

    RC --> SLLM
    RC --> SWH
    RC --> SSess
    RC --> STel
    RC -.injects.-> SSchema
    RC -.injects.-> SUM
    RVf --> SVer
    RA --> SLLM
    RA --> SAlerts
    RV --> SViews
    RM --> SUM
    RI --> SReg

    SAlerts --> SWH
    SAlerts --> SReg
    SViews --> SWH
    SSchema --> SWH
    SUM --> SWH
    SVer --> SLLM
    SVer --> SWH

    SReg --> ISlack
    SReg --> IEmail
    SReg --> IInApp

    SLLM -.uses.-> Prompts
    SLLM -.validates with.-> Models
    Routers -.raises.-> Errors

    SLLM -->|OpenAI HTTP| FM["Databricks FM API"]
    SWH -->|Thrift| WHs["Databricks SQL"]
    SAlerts -->|metric_sql + state writes| WHs
    SViews -->|saved sql + spec writes| WHs
    SSchema -->|information_schema reads| WHs
    SUM -->|user_memory writes| WHs
```

Source layout:

```
src/UnifiedIQ-api/app/
  main.py             FastAPI app + lifespan + CORS + exception handlers
                      + StaticFiles mount for the prebuilt UI
  config.py           Settings (BaseSettings) - all env vars in one class
  deps.py             AppState dataclass + FastAPI Depends helpers
  errors.py           Stable error codes + AppError type
  observability.py    JSON log formatter + OTel hook
  sse.py              SSE serializer with the fixed event vocabulary
  workers/            Lifespan start/stop hooks (sessions, telemetry, scheduler)

  routers/            health, chat, verify, integrations, alerts, views, memory
  services/           llm, warehouse, cache, auth, session_store, telemetry,
                      integration_registry, alerts, views, verifier, schema,
                      user_memory
  integrations/       base, slack, email_smtp, in_app
  models/             domain, requests, responses
  prompts/            chat_system, alert_system, verifier_system, judge_system

  catalog/ddl/        Generic + Databricks-flavored DDL
  eval/               Layered eval harness (L1-L4) + golden set + HTML report
```

Lifespan (`app/main.py`) does the wiring on startup: build `AppState`,
register concrete integrations (`Slack`, `Email`, `InApp`), ensure the
`unifiediq_alerts`, `user_views`, and `user_memory` Delta tables exist
(`CREATE TABLE IF NOT EXISTS` + idempotent `ALTER TABLE ADD COLUMNS`),
start background workers, and mount the static UI bundle if present.

## 3. Frontend

Stack: Next.js 15 (App Router, static export), React 19, TypeScript strict,
Tailwind CSS 4, Recharts, react-markdown + remark-gfm, lucide-react. No
Node server: the UI is built with `output: "export"` and FastAPI serves the
generated `out/` directory.

```mermaid
flowchart TB
    subgraph Pages["App router pages"]
      L["layout.tsx<br/>Providers + globals"]
      H["page.tsx -> /chat"]
      C["chat/page.tsx"]
      D["dashboard/page.tsx"]
    end

    subgraph Components
      direction LR
      Sidebar["Sidebar<br/>(suggestions + Recent chats +<br/>Memory + Alerts + Dashboard link)"]
      ChatPanel["ChatPanel<br/>(SSE consumer)"]
      Message["Message<br/>(markdown + ThinkingTrail + ResultView)"]
      Result["ResultView<br/>(KPI / Table / Bar / Line / Area / Pie + CSV + Pin + Verify)"]
      Verify["VerifyPanel<br/>(self-audit verdict + alt SQL)"]
      Pinned["PinnedView<br/>(rename / resize / drag / settings / refresh)"]
      Bell["NotificationsBell"]
      AlertsP["AlertsPanel"]
      MemoryP["MemoryPanel<br/>(/api/memory)"]
    end

    subgraph Contexts
      ConvCtx["ConversationContext<br/>(sessions[] + activeSessionId,<br/>persists per user_email)"]
      AlertCtx["AlertContext (toasts)"]
    end

    subgraph Lib
      ApiClient["api-client.ts<br/>(apiGet / apiPost / apiPatch / apiDelete / streamChat)"]
      SSE["sse.ts<br/>(async generator parser)"]
      Types["types.ts (mirror)"]
      Fmt["format.ts (numbers / CSV)"]
    end

    C --> Sidebar
    C --> ChatPanel
    ChatPanel --> Message
    Message --> Result
    Result --> Verify
    D --> Pinned
    Pinned --> Result
    Sidebar --> AlertsP
    Sidebar --> MemoryP
    Sidebar -.link.-> D
    C --> Bell
    D --> Bell

    ChatPanel --> ConvCtx
    AlertsP --> ApiClient
    Pinned --> ApiClient
    Bell --> ApiClient
    Verify --> ApiClient
    MemoryP --> ApiClient
    ChatPanel --> SSE
    ApiClient -.calls.-> Backend["/api/* (same origin)"]
```

The `ConversationContext` keeps a list of `ChatSession`s and one
`activeSessionId`, persisted under `unifiediq:sessions:{user_email}`
in `localStorage`. Each session has its own `turns[]`, auto-derived
title, and timestamps; the sidebar's *Recent chats* list lets the user
switch between them and previous chats survive *New chat*. A one-time
migration imports legacy single-thread storage so existing users don't
lose their last conversation.

## 4. Key flows

### 4.1 Streaming chat (`POST /api/chat/stream`)

The fixed SSE vocabulary is `thinking` / `sql` / `chart` / `data` /
`citation` / `done` / `error`. Streams always terminate with `done` or
`error` — never half-open.

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant API as FastAPI<br/>/api/chat/stream
    participant LLM as Databricks FM API<br/>(llama-3-3-70b)
    participant WH as Databricks SQL

    U->>API: POST {question, history, session_id?}
    API-->>U: event: thinking {step: "plan"}
    API->>LLM: chat_structured(SQLGenerationResponse)
    LLM-->>API: {intent, sql?, chart_config?, ...}

    alt intent == reject / clarify
      API-->>U: event: data {text}
    else intent == data / chart
      API->>API: sqlglot.transpile(databricks)
      API-->>U: event: sql {sql, assumptions}
      API-->>U: event: thinking {step: "query"}
      API->>WH: execute(sql)
      WH-->>API: rows
      API-->>U: event: chart {chart_config, data_snapshot}
      API-->>U: event: thinking {step: "summarize"}
      API->>LLM: stream(summary prompt)
      loop tokens
        LLM-->>API: token
        API-->>U: event: data {text}
      end
    end

    API->>API: persist SessionTurns + TelemetryEvent
    API-->>U: event: done {interaction_id, metadata}

    Note over API,U: on any failure -> event: error {code, message}
```

### 4.2 Alert lifecycle (NL → scheduled fire)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant API as /api/alerts
    participant LLM as Databricks FM API
    participant WH as Databricks SQL
    participant DB as workspace.default.<br/>unifiediq_alerts
    participant Sched as AlertScheduler
    participant Reg as IntegrationRegistry

    U->>API: POST {question, channel, recipient, scheduled_at}
    API->>LLM: chat_structured(AlertSpec)
    LLM-->>API: {title, metric_sql, comparator, threshold}
    API->>API: sqlglot validate + recipient validate
    API->>DB: INSERT (enabled=true)

    Note over Sched: wakes every ALERTS_POLL_INTERVAL_SECONDS<br/>(skips entirely when 0 active alerts)
    Sched->>DB: SELECT enabled = true
    DB-->>Sched: rows
    loop each due alert
      Sched->>WH: execute(metric_sql)
      WH-->>Sched: value
      alt value breaches threshold
        Sched->>Reg: in_app + (slack or email)
        Sched->>DB: UPDATE last_state='breached'
        opt scheduled_at set
          Sched->>DB: UPDATE enabled=false (one-shot)
        end
      else not breached
        Sched->>DB: UPDATE last_state='ok'
      end
    end
```

### 4.3 Pin to dashboard

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant Chat as Chat ResultView
    participant API as /api/views
    participant DB as workspace.default.user_views
    participant Dash as /dashboard page
    participant WH as Databricks SQL

    U->>Chat: Click Pin
    Chat->>U: prompt("Name this view")
    Chat->>API: POST {name, question, sql, chart_config, default_view}
    API->>API: sqlglot validate sql
    API->>DB: INSERT (spec as JSON)

    Note over U,Dash: later visit
    U->>Dash: open /dashboard
    Dash->>API: GET /api/views
    API->>DB: SELECT user_email
    DB-->>API: rows
    API-->>Dash: UserView[]
    loop each pinned view
      Dash->>API: POST /api/views/{id}/run
      API->>WH: execute(saved sql)
      WH-->>API: rows
      API-->>Dash: {view, rows}
      Dash->>Dash: render ResultView with saved spec
    end

    U->>Dash: edit (rename / resize / drag / settings)
    Dash->>API: PATCH /api/views/{id}<br/>{name?, spec patch}
    API->>API: merge + re-validate spec
    API->>DB: UPDATE
```

### 4.4 Self-audit (`POST /api/chat/verify`)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant API as /api/chat/verify
    participant LLM as Databricks FM API
    participant WH as Databricks SQL

    U->>API: POST {question, original_sql}
    API->>API: sqlglot validate original_sql
    API->>LLM: chat_structured(AlternativeSQLResponse)<br/>"compute the same metric a DIFFERENT way"
    LLM-->>API: {alternative_sql, approach, reject_reason?}
    API->>API: sqlglot validate alternative
    alt alternative ≡ original or rejected
      API-->>U: verdict=inconclusive, confidence=0
    else
      API->>WH: execute(original_sql)
      API->>WH: execute(alternative_sql)
      WH-->>API: rows_a, rows_b
      alt both scalar (single numeric)
        API->>API: relative-diff bands<br/>(≤1% / ≤5% / ≤20% / >)
        API-->>U: verdict + confidence + diff_pct
      else
        API->>LLM: chat_structured(JudgeScore)<br/>"compare these two result sets"
        LLM-->>API: {verdict, confidence, rationale}
        API-->>U: verdict + judge rationale
      end
    end
```

## 5. Cross-cutting concerns

### 5.1 Structured outputs

Every LLM call that drives application logic returns a validated Pydantic
model. `LLMService.chat_structured` patches the OpenAI client through
`instructor` in `Mode.MD_JSON` (fenced JSON, no
`response_format=json_object`). Databricks serving endpoints reject
`json_object` mode for these models, and reasoning models (`gpt-oss-*`)
return a parts list for `message.content` that breaks structured parsing.
The default model is `databricks-meta-llama-3-3-70b-instruct`, configurable
per environment.

### 5.2 Authentication

Three modes selected by `AUTH_MODE`, with `AUTH_BYPASS` as a local-only
escape hatch:

```mermaid
flowchart TB
    Req["Incoming /api/*"]
    Req --> Bypass{AUTH_BYPASS<br/>= true?}
    Bypass -- yes --> DevUser["CurrentUser<br/>= dev@localhost<br/>(honors X-User-Email)"]
    Bypass -- no --> Mode{AUTH_MODE}

    Mode -- bypass --> DevUser
    Mode -- databricks --> Fwd["read<br/>X-Forwarded-Email<br/>X-Forwarded-Preferred-Username"]
    Mode -- oidc --> Bearer{Authorization:<br/>Bearer present?}

    Fwd --> Resolved["CurrentUser<br/>(email, name, groups)"]
    Bearer -- no --> U401["401 UNAUTHENTICATED"]
    Bearer -- yes --> JWT["verify against<br/>Okta JWKS<br/>(audience + issuer)"]
    JWT --> Groups{OIDC_ALLOWED_GROUPS<br/>empty OR<br/>intersect claims.groups?}
    Groups -- no --> F403["403 FORBIDDEN"]
    Groups -- yes --> Resolved
```

### 5.3 Persistence

Three Databricks Delta tables in `<WAREHOUSE_CATALOG>.<WAREHOUSE_SCHEMA>`
(`workspace.default` in this deployment): `unifiediq_alerts`,
`user_views`, and `user_memory`. `chatbot_history`, `chatbot_sessions`,
and `eval_results` have DDL on disk but are not yet wired (the dev sinks
are in-memory). Chat session lists are stored client-side in
`localStorage` for now — see [memory_strategy.md](memory_strategy.md)
for the plan.

```mermaid
erDiagram
    UNIFIEDIQ_ALERTS {
        string id PK
        string user_email
        string title
        string natural_language
        string metric_sql
        string comparator "lt|lte|gt|gte|eq|neq"
        double threshold
        string channel "in_app|slack|email"
        string recipient
        int cadence_minutes
        boolean enabled
        string last_state "pending|ok|breached|error"
        double last_value
        timestamp last_checked_at
        timestamp scheduled_at "one-shot"
        timestamp created_at
    }

    USER_VIEWS {
        string view_id PK
        string user_email
        string name
        string kind "chart|table|dashboard"
        string spec "JSON: question, sql, chart_config, filter_text, layout, colors, x_label, y_label"
        boolean is_shared
        timestamp created_at
        timestamp updated_at
    }

    NOTIFICATIONS {
        string id PK
        string user_email
        string title
        string message
        string alert_id FK
        timestamp created_at
    }

    USER_MEMORY {
        string id PK
        string user_email
        string value "fact or preference, ≤500 chars"
        timestamp created_at
        timestamp updated_at
    }

    UNIFIEDIQ_ALERTS ||--o{ NOTIFICATIONS : "fires"
```

`ensure_table` runs on startup and includes an idempotent
`ALTER TABLE ... ADD COLUMNS` so additive column changes (e.g.
`scheduled_at`) migrate existing tables on next deploy. `Notification` is
in-process only (the bell's ring buffer); it is not persisted, but the
`alert_id` link is what enables auto-clearing of stale notifications when
an alert is deleted.

### 5.4 Async workers

All three workers run in-process; there is no external scheduler.

- `SessionStore` and `TelemetryLogger` use `asyncio.Queue` with batched
  flush every N items or T seconds (`worker_flush_max_items`,
  `worker_flush_interval_seconds`).
- `AlertScheduler` wakes every `ALERTS_POLL_INTERVAL_SECONDS` (default
  300) and calls `AlertService.evaluate_due()`. It maintains an in-process
  active-alert count: when zero, it **skips** the warehouse poll so the
  SQL warehouse can auto-suspend — no compute cost while idle.

### 5.5 Error model

`AppError(HTTPException)` carries a stable string code. Global handlers in
`app/main.py` translate `AppError` and `RequestValidationError` into a
consistent `{code, message, request_id}` shape. Streaming endpoints always
end with a terminal `error` SSE event on failure — never a half-open
stream.

Stable codes: `LLM_UNAVAILABLE`, `LLM_INVALID_OUTPUT`, `SQL_INVALID`,
`WAREHOUSE_TIMEOUT`, `WAREHOUSE_ERROR`, `INTEGRATION_NOT_FOUND`,
`INTEGRATION_ERROR`, `UNAUTHENTICATED`, `FORBIDDEN`, `BAD_REQUEST`,
`INTERNAL`.

### 5.6 Memory layers

The full plan and per-tier status live in
[memory_strategy.md](memory_strategy.md). What's wired today:

- **Tier 1 — schema grounding** (`SchemaService`): queries
  `<catalog>.information_schema.columns` for each `SCHEMA_SOURCES` entry,
  keyword-ranks the tables against the question, and renders an
  `"## Available tables"` block that the chat router prepends to the
  planner system prompt. Bounded by `SCHEMA_MAX_TABLES_INJECTED`, cached
  for `SCHEMA_TTL_SECONDS`. Failures are caught — chat still works if
  `information_schema` is unavailable.
- **Tier 4 — user memory** (`UserMemoryService` +
  `<schema>.user_memory` Delta table): persistent per-user facts. The
  chat router also renders these as an `"## User context"` bullet list
  in the system prompt. Managed by the sidebar Memory panel
  (`GET/POST/DELETE /api/memory`).

Tiers 2 (result cache), 3 (rolling summary), and 5 (episodic recall via
Vector Search) are planned; see `memory_strategy.md` for design.

### 5.7 Self-audit (verifier)

`VerifierService` (see §4.4) is the runtime "BI tools don't admit
uncertainty" feature: it asks the LLM for a *structurally different*
alternative SQL (`AlternativeSQLResponse`), runs both queries, and
either compares scalars within tolerance bands (1% / 5% / 20%) or
falls back to `llm_judge` (`JudgeScore` over the two result sets). The
same `llm_judge()` function is exported so the eval harness's L4 layer
can reuse it.

## 6. Evaluation framework

`src/UnifiedIQ-api/eval/` ships a layered harness:

| Layer | Check                                                            |
|-------|------------------------------------------------------------------|
| L1    | `sqlglot.transpile(dialect="databricks")` parses the SQL         |
| L2    | Intent / required + forbidden regex / expected columns / chart   |
| L3    | Execution parity: generated vs expected SQL row counts (opt-in)  |
| L4    | Stubbed LLM-as-judge                                             |

`run_eval.py --golden eval/golden_test_set.json [--run-l3] [--write-report]`
emits `results/<git-sha>-<ts>.json` (matching the `eval_results` schema)
and, with `--write-report`, an inline-CSS HTML report (scorecard,
failure-tag histogram, per-case diffs).

## 7. CI/CD

`.github/workflows/ci.yml` uses path-based change detection
(`dorny/paths-filter`) and runs the standard pipeline. `push` and `deploy`
jobs are guarded by secret presence — a fresh clone has a green pipeline
without infra credentials.

```mermaid
flowchart LR
    Trig{Trigger}
    Trig -- pull_request --> Changes
    Trig -- push main --> Changes
    Trig -- schedule cron --> NL3

    Changes["changes<br/>(dorny/paths-filter:<br/>api / ui)"]
    Changes --> Lint
    Lint["lint<br/>ruff + ruff-format + eslint"]
    Lint --> Test
    Test["test<br/>pytest + tsc --noEmit + next build"]

    Test --> Eval
    Eval["eval (PR-only)<br/>L1 + L2<br/>upload report artifact"]

    Test --> Build
    Build["build<br/>docker build api + ui"]
    Build --> Push
    Push["push (main only)<br/>guarded by REGISTRY secret"]
    Push --> Deploy
    Deploy["deploy (main only)<br/>guarded by DEPLOY_HOST secret"]

    NL3["eval-nightly-l3<br/>L1+L2+L3 via cron"]
```

## 8. Configuration

All backend settings live in `app/config.py` as a single
`Settings(BaseSettings)`. Every variable read by code appears in
`src/UnifiedIQ-api/.env.example`. Key groups: app, LLM (Databricks FM API),
warehouse (Databricks SQL), vector store, OIDC auth, service principal,
cache, workers, alerts, Slack, SMTP. The frontend has one client variable
(`NEXT_PUBLIC_APP_NAME`) in `products/UnifiedIQ-ui/.env.example`.

For Databricks deployment,
[`src/UnifiedIQ-api/app.yaml`](src/UnifiedIQ-api/app.yaml) declares the
`command` (uvicorn binding to `$DATABRICKS_APP_PORT`), non-secret env
values, and `valueFrom` references to secret-scope keys. Secrets are kept
out of source via the `unifiediq` Databricks secret scope.
