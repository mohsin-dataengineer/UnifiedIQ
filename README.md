# UnifiedIQ

An AI-powered, conversational business-intelligence platform over a
Databricks SQL warehouse. Ask a question in plain English, get a streamed
answer with the generated SQL, an interactive chart, KPI cards, and a row
table. Pin anything useful into a durable, editable dashboard, or turn it
into an always-on alert that fires at a scheduled time over Email or Slack.

Deploys as a **single Databricks App** (FastAPI process serves both the API
and a prebuilt Next.js static SPA), or as a **two-tier Docker Compose**
stack (Next.js BFF + FastAPI API + optional Postgres) for local
development.

## Highlights

- **Conversational text-to-SQL with structured outputs.** Every LLM call
  returns a validated Pydantic model; the assistant picks one of four intents
  (`data` / `chart` / `clarify` / `reject`) so it never guesses wildly.
- **Live streaming UX.** Server-Sent Events show the assistant's reasoning,
  the generated SQL, the chart, and the narrative answer token-by-token —
  with a hard guarantee that the stream always ends with `done` or `error`,
  never half-open.
- **Interactive result view.** Every answer renders as a KPI card, table,
  or switchable Bar / Line / Area / Pie chart with CSV export.
- **Self-auditing answers.** A *Verify* button on every numeric answer
  asks the LLM to derive the same metric a structurally different way,
  re-runs both queries, and reports `agree` / `disagree` / `inconclusive`
  with a confidence pill, relative-diff %, and the alternative SQL.
- **Multi-session chat history.** Every conversation is auto-titled from
  the first user message and saved per `user_email`. A *Recent chats* list
  in the sidebar switches between threads; new chat preserves the old one
  instead of wiping it.
- **Schema-grounded prompts (Memory · Tier 1).** The planner system message
  is augmented with the user's actual warehouse tables and columns (pulled
  from `information_schema`, cached), so the model stops inventing names.
- **User memory (Memory · Tier 4).** A sidebar panel stores persistent
  facts the assistant should keep in mind across every chat ("fiscal year
  starts in April"). Backed by a Delta table keyed by `user_email`.
- **Pin-to-dashboard.** Pin any chat result; the dashboard re-runs the
  saved SQL on load. Each card supports inline rename, resize (S/M/L),
  drag-and-drop reorder, axis labels, custom series colors, and a row
  filter. Layout persists in a Databricks Delta table.
- **Natural-language alerts.** "Alert me when daily signups drop below
  1000." The model compiles the metric SQL + threshold; an in-process
  scheduler runs it at the date/time you pick and fires via Email, Slack,
  or the in-app notifications bell.
- **Built-in evaluation harness.** L1 (sqlglot syntax) → L2 (structure +
  expected columns/chart) → L3 (execution parity, opt-in) → L4 (stubbed
  LLM judge), with JSON and inline-CSS HTML reports per run.
- **Cost-aware scheduling.** When no alerts exist, the warehouse polling
  loop short-circuits — the SQL warehouse auto-suspends and no compute is
  billed.

## Quickstart

### Option 1 — Run on Databricks Apps (production-style)

Prereqs: Databricks CLI ≥ 0.230, a SQL Warehouse, and the
`databricks-meta-llama-3-3-70b-instruct` serving endpoint enabled in your
workspace.

```bash
# 1. Authenticate the CLI to your workspace
databricks auth login --host https://<your-workspace-host>

# 2. Create a secret scope and store a PAT (used for LLM + warehouse + service)
export DBX_TOKEN='dapi...'
databricks secrets create-scope unifiediq
for k in llm_api_key warehouse_token service_token; do
  databricks secrets put-secret unifiediq "$k" --string-value "$DBX_TOKEN"
done

# 3. Edit the workspace host + warehouse id in src/UnifiedIQ-api/app.yaml

# 4. Create the app, sync, and deploy
cd src/UnifiedIQ-api
databricks apps create unifiediq-api
databricks sync . "/Workspace/Users/<your-userName>/unifiediq-api"
databricks apps deploy unifiediq-api \
  --source-code-path "/Workspace/Users/<your-userName>/unifiediq-api"

# 5. Open the URL printed by `databricks apps get unifiediq-api`
```

The Databricks App reads identity from the platform's `X-Forwarded-*`
headers (`AUTH_MODE=databricks`) — no Okta or local auth needed. See
[Architecture.md](Architecture.md) for the auth and persistence model.

### Option 2 — Local two-tier (Docker Compose)

```bash
cp src/UnifiedIQ-api/.env.example     src/UnifiedIQ-api/.env
cp products/UnifiedIQ-ui/.env.example products/UnifiedIQ-ui/.env.local
# Fill in your Databricks host/PAT/warehouse and (optionally) Okta values.
# Or set AUTH_BYPASS=true in both files to skip identity entirely.

make dev   # docker compose: api :5000, ui :3000, db :5432
```

Common targets:

| Target       | What it does                                       |
|--------------|----------------------------------------------------|
| `make dev`   | `docker compose up --build`                        |
| `make down`  | `docker compose down`                              |
| `make test`  | pytest + UI tests in parallel                      |
| `make eval`  | layered eval; writes JSON + HTML to `eval/results/` |
| `make fmt`   | `ruff format` + `prettier --write`                 |
| `make lint`  | `ruff check` + `eslint`                            |

### Backend-only iteration (no Docker)

```bash
cd src/UnifiedIQ-api
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload --port 5000
```

Python 3.12 is required by `pyproject.toml`. If your system Python is 3.11,
`uv` (or `pyenv`) will fetch 3.12 transparently.

## Documentation

- **[Architecture.md](Architecture.md)** — runtime topology, backend layers
  (routers / services / models / prompts / workers / eval), frontend
  layout, SSE event vocabulary, auth modes (`oidc` | `databricks` | `bypass`),
  persistence, error model, CI/CD. Includes the hand-authored
  [assets/architecture.svg](assets/architecture.svg) system-context diagram
  plus Mermaid sequence/ER diagrams for technical flows.
- **[ConversationalBI.md](ConversationalBI.md)** — chat experience: result
  card, view switcher, suggested prompts, multi-session history, alerts
  panel, notifications bell, the *Verify* self-audit panel, the Memory
  panel, identity.
- **[Dashboard.md](Dashboard.md)** — pinning from chat, per-card controls
  (rename, resize, drag-reorder, axis labels, colors, filter), persistence
  in `user_views`, layout model.
- **[memory_strategy.md](memory_strategy.md)** — the five-tier memory
  roadmap (schema awareness, result cache, rolling summary, user memory,
  episodic recall), with per-tier design and current status.
- **[CHANGELOG.md](CHANGELOG.md)** — chronological log of feature drops
  in this build.
- **[CLAUDE.md](CLAUDE.md)** — operating notes for Claude Code
  (commands, deploy flow, non-obvious architecture choices).

## Repository layout

```
src/UnifiedIQ-api/         FastAPI backend, catalog DDL, eval framework, tests
  app/                       FastAPI app, routers, services, integrations
  catalog/ddl/               Warehouse-agnostic DDL with Databricks notes
  eval/                      Golden set + layered eval runner + HTML report
  tests/                     pytest suite (asyncio_mode = auto)
  app.yaml                   Databricks Apps manifest
  requirements.txt           Runtime deps installed by Databricks Apps
  Dockerfile                 Local two-tier image

products/UnifiedIQ-ui/      Next.js 15 static SPA (App Router, `output: export`)
  src/app/chat/              Chat experience
  src/app/dashboard/         Pinned dashboard
  src/components/            ChatPanel, ResultView, PinnedView, etc.
  src/lib/                   API client, SSE reader, types, formatters

docker-compose.yml          api + ui + optional Postgres
Makefile                    dev / test / eval / fmt / lint
.pre-commit-config.yaml     ruff, ruff-format, eslint, prettier
.github/workflows/ci.yml    lint -> test -> eval -> build -> push -> deploy
Architecture.md             System architecture (Mermaid + SVG diagrams)
ConversationalBI.md         Chat + alerts + verify + memory walkthrough
Dashboard.md                Pin-to-dashboard feature walkthrough
memory_strategy.md          Five-tier memory roadmap + status
CHANGELOG.md                Chronological feature drops
CLAUDE.md                   Notes for Claude Code
assets/architecture.svg     Hand-authored system-context diagram
```

## Configuration at a glance

Every backend setting lives in `app/config.py` and is documented in
`src/UnifiedIQ-api/.env.example`. Key choices made in this build:

| Field                  | Value                                          |
|------------------------|------------------------------------------------|
| Warehouse              | Databricks SQL                                 |
| LLM provider           | Databricks Foundation Model API                |
| Default model          | `databricks-meta-llama-3-3-70b-instruct`       |
| Structured outputs     | `instructor` Mode.MD_JSON                      |
| Auth modes             | `oidc` (Okta) / `databricks` (SSO headers) / `bypass` |
| Persistence            | Databricks Delta tables (`unifiediq_alerts`, `user_views`, `user_memory`) in `workspace.default` |
| Deployment             | Databricks Apps (single process) OR Docker Compose (two tier) |
| CI/CD                  | GitHub Actions                                 |
| Day-one integrations   | Slack, Email (SMTP), in-app notifications      |
