# UnifiedIQ Agent Guide

## Project Overview

UnifiedIQ is a conversational business-intelligence app over Databricks SQL.
The production-style deployment is a single Databricks App: FastAPI serves
all `/api/*` routes and also serves the prebuilt Next.js static export from
`src/UnifiedIQ-api/static/`.

Local development can also run as a two-tier Docker Compose stack:

- API: FastAPI on port `5000`
- UI: Next.js on port `3000`
- Optional Postgres: port `5432`

Start with these docs before non-trivial changes:

- `README.md` for product scope, quickstart, and repository layout.
- `Architecture.md` for runtime topology, auth, persistence, SSE, and CI/CD.
- `ConversationalBI.md` for chat, alerts, verify, memory, and chat history.
- `Dashboard.md` for pinned dashboard behavior.
- `memory_strategy.md` for memory tiers.
- `CHANGELOG.md` for what shipped when.
- `CLAUDE.md` for deployment notes and workspace-specific Databricks values.

## Repository Layout

```text
src/UnifiedIQ-api/         FastAPI backend, Databricks App manifest, tests, eval
  app/                       config, deps, routers, services, models, prompts
  catalog/ddl/               Delta/warehouse DDL
  eval/                      layered eval runner and golden set
  static/                    built Next.js static export served by FastAPI
  tests/                     pytest suite

products/UnifiedIQ-ui/      Next.js 15 static SPA
  src/app/                   App Router pages and providers
  src/components/            chat, dashboard, and shared UI components
  src/contexts/              React context state
  src/lib/                   API client, SSE reader, env, types, formatters

assets/                    diagrams and static documentation assets
.github/workflows/ci.yml   lint/test/eval/build workflow
docker-compose.yml         local API + UI + Postgres stack
Makefile                   root command shortcuts
```

## Source of Truth

- Backend settings are defined in `src/UnifiedIQ-api/app/config.py`.
- Backend env examples must stay in sync with `src/UnifiedIQ-api/.env.example`.
- Databricks App runtime env is in `src/UnifiedIQ-api/app.yaml`.
- UI build/runtime behavior is defined by `products/UnifiedIQ-ui/next.config.ts`.
- UI is currently a static export (`output: "export"`). Do not add Next route
  handlers, middleware, server-only auth flows, or server components that require
  a Node runtime unless the deployment model changes.
- Some UI comments/docs may still mention a BFF/NextAuth setup; current code and
  `next.config.ts` indicate same-origin static SPA behavior served by FastAPI.

## Toolchain

Backend:

- Python `>=3.12`
- FastAPI, Pydantic v2, pydantic-settings
- Databricks SQL connector and Vector Search
- OpenAI-compatible Databricks Foundation Model API
- `instructor` structured outputs with `Mode.MD_JSON`
- `sqlglot` using Databricks dialect
- Ruff for lint/format
- Pytest with `asyncio_mode = auto`

Frontend:

- Node `22` in CI
- Next.js `15.1.0`
- React `19`
- TypeScript strict mode
- Tailwind CSS 4
- Recharts, react-markdown, remark-gfm
- lucide-react icons
- ESLint flat config with Next core web vitals/typescript rules
- Prettier
- Vitest (`--passWithNoTests`)

## Common Commands

From the repo root:

```bash
make dev      # docker compose up --build
make down     # docker compose down
make test     # backend pytest and UI tests in parallel
make eval     # API eval harness, writes reports under eval/results/
make fmt      # ruff format + prettier
make lint     # ruff check + eslint
```

Backend-only:

```bash
cd src/UnifiedIQ-api
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
uvicorn app.main:app --reload --port 5000
python eval/run_eval.py --golden eval/golden_test_set.json --write-report
```

Frontend-only:

```bash
cd products/UnifiedIQ-ui
npm install
npm run dev
npm run lint
npm run typecheck
npm test
SKIP_ENV_VALIDATION=1 npm run build
```

CI runs path-gated lint/test jobs. API changes run Ruff and pytest. UI changes
run ESLint, TypeScript, and `next build`.

## Configuration

Backend local setup:

```bash
cp src/UnifiedIQ-api/.env.example src/UnifiedIQ-api/.env
```

UI local setup:

```bash
cp products/UnifiedIQ-ui/.env.example products/UnifiedIQ-ui/.env.local
```

Important backend settings:

- `AUTH_MODE=oidc | databricks`
- `AUTH_BYPASS=true` overrides auth for local development only.
- `WAREHOUSE_CATALOG` and `WAREHOUSE_SCHEMA` choose the writable Delta schema.
- Empty `ALERTS_TABLE` resolves to
  `<WAREHOUSE_CATALOG>.<WAREHOUSE_SCHEMA>.unifiediq_alerts`.
- Empty `USER_MEMORY_TABLE` resolves to
  `<WAREHOUSE_CATALOG>.<WAREHOUSE_SCHEMA>.user_memory`.
- `SCHEMA_SOURCES` is a comma-separated list of `<catalog>.<schema>` sources
  for schema grounding.

The Databricks App deployment uses `AUTH_MODE=databricks` and trusts
Databricks-injected `X-Forwarded-*` identity headers.

## Backend Conventions

- Keep routes in `app/routers/`.
- Keep business logic and integrations in `app/services/` or
  `app/integrations/`.
- Keep request/response/domain models in `app/models/`.
- Keep LLM prompt text in `app/prompts/`.
- All application logic driven by LLM output should use validated Pydantic
  structured models, not free-form parsing.
- Preserve the stable error response shape from `app/main.py`:
  `{code, message, request_id}` for handled errors.
- Prefer raising `AppError` with a stable code from `app/errors.py`.
- `ensure_table` methods should be idempotent and additive. Do not drop or
  recreate user data tables as a migration shortcut.
- Async background workers are managed through app lifespan startup/shutdown.

### SSE Contract

`POST /api/chat/stream` emits a fixed event vocabulary:

- `thinking`
- `sql`
- `chart`
- `data`
- `citation`
- `done`
- `error`

Every stream must terminate with either `done` or `error`.

## Frontend Conventions

- The UI is a static SPA. Browser API calls are same-origin `/api/*` calls.
- State is React Context based; do not introduce Redux/Zustand/Jotai without a
  clear architectural need.
- Use the existing component organization under `src/components/chat`,
  `src/components/dashboard`, and `src/components/ui`.
- Use the `@/*` TypeScript path alias for imports from `src`.
- Keep TypeScript strict and avoid weakening types to move faster.
- Use lucide-react icons when an icon exists.
- Keep UI changes compatible with static export and FastAPI static serving.
- Any change under `products/UnifiedIQ-ui/src/` requires rebuilding the static
  export and copying it into `src/UnifiedIQ-api/static/` before Databricks App
  deployment.

Static UI rebuild for deployment:

```bash
cd products/UnifiedIQ-ui
rm -rf .next out
SKIP_ENV_VALIDATION=1 npm run build
cp -R out ../../src/UnifiedIQ-api/static
```

## Testing Expectations

- Backend tests live in `src/UnifiedIQ-api/tests/`.
- `pytest.ini` enforces coverage with `--cov=app --cov-fail-under=70`.
- Use focused pytest runs while iterating, then run the relevant broader suite.
- For API router/service changes, add or update pytest coverage.
- For UI changes, run at least `npm run lint`, `npm run typecheck`, and
  `SKIP_ENV_VALIDATION=1 npm run build` when feasible.
- For chat, streaming, auth, deployment, or Databricks integration changes,
  local unit tests are not enough; run a runtime smoke where practical.

## Deployment Notes

The Databricks App deploys from `src/UnifiedIQ-api/`. UI assets must already
be present in `src/UnifiedIQ-api/static/`.

Typical deploy flow:

```bash
cd products/UnifiedIQ-ui
rm -rf .next out
SKIP_ENV_VALIDATION=1 npm run build
cp -R out ../../src/UnifiedIQ-api/static

cd ../../src/UnifiedIQ-api
databricks sync . "/Workspace/Users/<user>/unifiediq-api" -p unifiediq
databricks apps deploy unifiediq-api \
  --source-code-path "/Workspace/Users/<user>/unifiediq-api" -p unifiediq
databricks apps get unifiediq-api -p unifiediq -o json
```

Do not assume `databricks apps logs` works with PAT auth; reproduce locally
against the same Databricks host when logs are unavailable.

## Git and Generated Files

- The worktree may contain user edits. Do not revert unrelated changes.
- `products/UnifiedIQ-ui/tsconfig.tsbuildinfo`, `.next/`, `out/`,
  `node_modules/`, virtualenvs, and generated eval reports should not be
  hand-edited.
- `src/UnifiedIQ-api/static/` contains generated UI build output. Update it via
  the static rebuild flow, not manual edits.
- When committing in this repo, do not add generated-agent attribution trailers
  such as `Co-Authored-By` or `Generated with ...`.

## Pre-Commit and Formatting

`.pre-commit-config.yaml` runs:

- Ruff and Ruff format for `src/UnifiedIQ-api/`
- ESLint for UI TypeScript/TSX
- Prettier for UI TS/TSX/CSS/JSON

Use the existing formatters instead of hand-formatting large diffs.
