# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview about UnifiedIQ

**What this is.** UnifiedIQ — a conversational-BI app over Databricks SQL.
Deployed as a single Databricks App that serves both `/api/*` (FastAPI)
and the prebuilt Next.js static SPA from `src/UnifiedIQ-api/static/`.

**Live deploy:** https://unifiediq-api-7474659305259840.aws.databricksapps.com
(Databricks SSO; open in a browser where you're logged into the workspace).

**Shipped today** — text-to-SQL chat with SSE streaming, switchable
KPI / Table / Bar / Line / Area / Pie result view, Pin-to-dashboard with
rename / resize / drag-reorder / settings popover, natural-language
alerts with date-time scheduling + Email/Slack/in-app channels,
self-auditing answers (`/api/chat/verify`), multi-session chat history,
and memory tiers 1 (schema grounding) + 4 (user memory).

**Read order by intent** (don't grep blind — these docs are kept current):

| You want to…                                | Start here                                        |
|---------------------------------------------|---------------------------------------------------|
| Understand the runtime + how pieces fit     | [Architecture.md](Architecture.md) §1–§3          |
| Change anything in the chat experience      | [ConversationalBI.md](ConversationalBI.md)        |
| Change anything in the pinned dashboard     | [Dashboard.md](Dashboard.md)                      |
| Touch storage / Delta tables / persistence  | [Architecture.md](Architecture.md) §5.3           |
| Plan or ship a new memory tier              | [memory_strategy.md](memory_strategy.md)          |
| See what shipped when                       | [CHANGELOG.md](CHANGELOG.md)                      |
| Deploy / redeploy                           | the *Deploying to the Databricks App* section below |

**First sanity check** when picking up cold: `databricks apps get unifiediq-api -p unifiediq -o json | jq .app_status` should report `RUNNING`. Then open the URL and ask *"How many trips are in samples.nyctaxi.trips?"* — you should see `thinking → sql → chart → data → done` with a KPI of **21,932**.

## Working style the user expects

- **Phased execution.** When given a multi-step task, execute one phase at a
  time, stop, and wait for an explicit "yes" before continuing. At the end
  of each phase report in this exact shape: *files changed · decisions made
  · next step*. Keep scope to the current phase only — no opportunistic
  refactors. Flag deviations from spec explicitly with rationale.
- **Validate before claiming "done".** A phase isn't complete until tests +
  lint + build pass, *and* a runtime/integration smoke (uvicorn + curl, or
  a real UI render) succeeds for any chat/streaming/UI change.
- **Commit attribution.** When committing on this repo,
  The repo's `git user.name`/`user.email` are already set to the owner; let
  default authorship stand.
- **TodoWrite** belongs to multi-step tracked work; skip it for single
  focused edits.

Long-form docs to read before non-trivial changes:
[README.md](README.md), [Architecture.md](Architecture.md) (includes
mermaid + the hand-authored `assets/architecture.svg`),
[ConversationalBI.md](ConversationalBI.md), [Dashboard.md](Dashboard.md),
[memory_strategy.md](memory_strategy.md) (five-tier memory roadmap with
status), [CHANGELOG.md](CHANGELOG.md) (what shipped when).

## Toolchain

The host typically only has Python 3.11; the backend requires 3.12. Use
`uv` to provision:

```bash
cd src/UnifiedIQ-api
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

`pytest.ini` enforces 70% coverage. Run from `src/UnifiedIQ-api/`:

```bash
pytest                                      # full suite
pytest tests/test_routers_chat.py -k clarify  # single test
ruff check . && ruff format --check .
```

Frontend (from `products/UnifiedIQ-ui/`):

```bash
npm install
npx tsc --noEmit
npx eslint .
SKIP_ENV_VALIDATION=1 npm run build         # required: env.ts parses at import
```

Repo-root Makefile aggregates: `make test`, `make lint`, `make eval`,
`make dev` (docker compose), `make down`.

Eval harness:

```bash
cd src/UnifiedIQ-api
python eval/run_eval.py --golden eval/golden_test_set.json --write-report
# results land in eval/results/<git-sha>-<ts>.{json,html}
```

## Deploying to the Databricks App

The Databricks App runs a single FastAPI process serving both `/api/*` and
the prebuilt static SPA from `src/UnifiedIQ-api/static/`. **UI changes
require rebuilding and copying the bundle before sync.**

```bash
# 1. Rebuild static SPA
cd products/UnifiedIQ-ui && rm -rf .next out
SKIP_ENV_VALIDATION=1 npm run build
cp -R out ../../src/UnifiedIQ-api/static

# 2. Sync + deploy (profile already configured at ~/.databrickscfg [unifiediq])
cd ../../src/UnifiedIQ-api
databricks sync . "/Workspace/Users/mohsin.it.se@gmail.com/unifiediq-api" -p unifiediq
databricks apps deploy unifiediq-api \
  --source-code-path "/Workspace/Users/mohsin.it.se@gmail.com/unifiediq-api" -p unifiediq
databricks apps get unifiediq-api -p unifiediq -o json  # check status
```

`databricks apps logs` does **not** work with PAT auth (needs OAuth). To
diagnose runtime issues, reproduce the call locally against the real
Databricks endpoint using `.env`, which has the host + PAT pre-configured.

## Architecture cheatsheet (the bits you can't see from one file)

**Single-process deploy.** `app/main.py` mounts `StaticFiles` at `/` after
all `/api/*` routers, so the same FastAPI process serves the SPA and the
API. There is **no Node BFF in production** — the Next.js app is built with
`output: "export"` and ships as static assets. Don't add route handlers,
NextAuth, middleware, or server components with `redirect()` to the SPA —
they'd require a Node server.

**LLM via instructor MD_JSON, not JSON.** `LLMService` in
`app/services/llm.py` uses `instructor.Mode.MD_JSON`. Databricks serving
endpoints reject `response_format={"type":"json_object"}` unless the
messages literally contain "json", and the constraint is finicky. MD_JSON
sidesteps it by asking for fenced JSON. **Default model:**
`databricks-meta-llama-3-3-70b-instruct`. **Avoid GPT-OSS** (`gpt-oss-20b`,
`gpt-oss-120b`) — they're reasoning models whose `message.content` is a
parts list (`[{type:"reasoning"...},{type:"text",...}]`) that breaks
structured-output parsing.

**Fixed SSE vocabulary.** `POST /api/chat/stream` emits only:
`thinking`, `sql`, `chart`, `data`, `citation`, `done`, `error`. The stream
must always terminate with `done` or `error` — never half-open. The chat
router emits a `chart` event on **every** data answer (not only when the
LLM picks chart intent) so the UI can render KPI/table/chart from one
payload.

**Structured-output-first.** Every LLM call that drives application logic
returns a validated Pydantic model: `SQLGenerationResponse` (chat),
`AlertSpec` (alerts), `AlternativeSQLResponse` + `JudgeScore` (verify),
`AlertChannel`/`ViewSpec` patches (PATCH endpoints). No free-form parsing
of LLM output anywhere in the app code.

**Routes.** Endpoints worth knowing about: `/api/chat` and
`/api/chat/stream` (SSE), `/api/chat/verify` (self-audit),
`/api/views` (CRUD + `PATCH` + `/run`), `/api/alerts` (CRUD + `/run`),
`/api/notifications`, `/api/memory` (CRUD — user_memory facts),
`/api/integrations`, `/api/me`, `/api/health`.

**Persistence.** Three Delta tables in
`<WAREHOUSE_CATALOG>.<WAREHOUSE_SCHEMA>` (`workspace.default` in this
deployment):

| Table                | Service                       | What's in `spec`                           |
|----------------------|-------------------------------|---------------------------------------------|
| `unifiediq_alerts`   | `app/services/alerts.py`      | flat columns; `scheduled_at` is one-shot   |
| `user_views`         | `app/services/views.py`       | JSON: question, sql, chart_config, filter_text, layout, colors, x/y_label, default_view |
| `user_memory`        | `app/services/user_memory.py` | flat (`value` text per row, per user)      |

`ensure_table` runs in lifespan with **idempotent** `ALTER TABLE ADD COLUMNS`
so additive schema changes migrate on next deploy. Don't drop/recreate.

**Memory (Tiers 1 & 4) live in `_build_messages`.** The chat router's
planner system prompt is now built dynamically:
`SQL_GENERATION_SYSTEM + schema_block + user_memory_block`.
- `SchemaService.context_block(question)` (Tier 1) queries
  `<catalog>.information_schema.columns` for each source in
  `SCHEMA_SOURCES`, caches with TTL, keyword-ranks tables against the
  question, and produces an `"## Available tables"` block.
- `UserMemoryService.context_block(user_email)` (Tier 4) fetches the
  user's persisted facts and renders as a bullet list.
Both layers are wrapped in `try/except` so chat still works if one
fails. See [memory_strategy.md](memory_strategy.md) for the full plan.

**Self-audit (verify).** `VerifierService.verify` asks the LLM for a
*structurally different* alternative SQL via `AlternativeSQLResponse`,
runs both queries, prefers a numeric-tolerance compare (1% / 5% / 20%
bands), and falls back to `llm_judge` (same function the eval harness's
L4 can reuse — keeps the loop closed). `Mode.MD_JSON` again.

**Chat sessions (multi-thread).** The frontend stores sessions in
`localStorage` under `unifiediq:sessions:{user_email}` as
`{sessions: ChatSession[], activeSessionId}`. There's a one-time
migration from the legacy single-thread key. Backend isn't involved
in chat-list persistence (yet).

**Auth (`AUTH_MODE`).** Three modes selected at runtime by
`UserAuthService`:
- `databricks` (production on the App) — trusts `X-Forwarded-Email` and
  `X-Forwarded-Preferred-Username` injected by the platform after SSO.
- `oidc` — validates `Authorization: Bearer` against Okta JWKS + audience
  + issuer, enforces `OIDC_ALLOWED_GROUPS`.
- `AUTH_BYPASS=true` overrides everything for local dev → returns a
  synthetic `dev@localhost` user.

**Async workers.** All in-process asyncio tasks managed in
`app/workers/__init__.py`, started in lifespan:
- `SessionStore` / `TelemetryLogger` — batched queue flush.
- `AlertScheduler` — `evaluate_due()` every `ALERTS_POLL_INTERVAL_SECONDS`
  (default 300). **Skips the warehouse poll entirely when the in-process
  active-alert count is zero** so the SQL warehouse auto-suspends. Don't
  remove this short-circuit; it's a real-cost concern on the user's trial.

**Error model.** Handled errors raise `AppError` with a stable string code
(`LLM_UNAVAILABLE`, `LLM_INVALID_OUTPUT`, `SQL_INVALID`, `WAREHOUSE_TIMEOUT`,
`WAREHOUSE_ERROR`, `INTEGRATION_NOT_FOUND`, `INTEGRATION_ERROR`,
`UNAUTHENTICATED`, `FORBIDDEN`, `BAD_REQUEST`, `INTERNAL`). Global handlers
in `app/main.py` translate everything to `{code, message, request_id}`.

## Workspace-specific values (this deployment)

- Workspace host: `dbc-85b951c8-d6b2.cloud.databricks.com`
- Warehouse path: `/sql/1.0/warehouses/0487a6bd3a272a77`
- Writable schema (used by the app): `workspace.default`. The
  brief's `main.analytics` does **not** exist in trial workspaces — leave
  `WAREHOUSE_CATALOG=workspace`, `WAREHOUSE_SCHEMA=default` for both alerts
  and views.
- Secret scope: `unifiediq` (keys: `llm_api_key`, `warehouse_token`,
  `service_token`).
- App: `unifiediq-api`, URL `https://unifiediq-api-7474659305259840.aws.databricksapps.com`.
- CLI profile name: `unifiediq` in `~/.databrickscfg`.

## Configuration

`app/config.py` is the single source of truth for env vars
(`Settings(BaseSettings)`). Every variable read by code must appear in
`src/UnifiedIQ-api/.env.example` — keep that file in sync when adding
settings. The frontend has one public var (`NEXT_PUBLIC_APP_NAME`) in
`products/UnifiedIQ-ui/.env.example`; the rest is built-time-inlined.
The Databricks App reads the same env from
[`src/UnifiedIQ-api/app.yaml`](src/UnifiedIQ-api/app.yaml) (non-secret as
`value`, secrets as `valueFrom: <resource-name>` referencing the
`unifiediq` secret scope via app *resources*).

## When changes need a static rebuild

Any change under `products/UnifiedIQ-ui/src/` requires the static rebuild
+ copy step before `databricks sync`/`databricks apps deploy` will pick it
up. Changes under `src/UnifiedIQ-api/app/` only need a re-sync + redeploy
(no rebuild). Backend tests (`pytest`) cover routers + services with
faked LLM/warehouse; a green local suite does not guarantee Databricks-side
behavior (auth, instructor mode, schema names), so for streaming/LLM/auth
changes run the live curl smoke against the deployed app or the local
backend hitting the real Databricks endpoint.
