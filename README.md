# UnifiedIQ

AI-powered business intelligence platform that unifies enterprise data,
semantic metrics, and conversational analytics into a governed, real-time
insight experience.

## Architecture

- **`src/UnifiedIQ-api/`** — Python 3.12 / FastAPI backend. Text-to-SQL over
  Databricks SQL, RAG via Databricks Vector Search, LLM calls via the
  Databricks Foundation Model API (OpenAI-compatible), structured outputs with
  `instructor`, SSE streaming, async-queue telemetry/session workers.
- **`products/UnifiedIQ-ui/`** — Next.js 15 / React 19 frontend. BFF proxy
  pattern (browser never calls the API directly), NextAuth v5 + Okta OIDC.

The browser talks only to Next.js Route Handlers, which authenticate the user
and forward to the API with a bearer token and identity headers.

## Quickstart

```bash
cp src/UnifiedIQ-api/.env.example src/UnifiedIQ-api/.env
cp products/UnifiedIQ-ui/.env.example products/UnifiedIQ-ui/.env.local
# Fill in Databricks + Okta values, or set AUTH_BYPASS=true in both for local dev.
make dev          # docker compose: api :5000, ui :3000, db :5432
```

| Target | What it does |
|---|---|
| `make dev`  | `docker compose up --build` |
| `make down` | `docker compose down` |
| `make test` | pytest + UI tests in parallel |
| `make eval` | run the layered eval and write JSON + HTML reports |
| `make fmt`  | ruff format + prettier |
| `make lint` | ruff check + eslint |

## Configuration

Confirmed Part 0 selections:

| Field | Value |
|---|---|
| Warehouse | Databricks SQL |
| Vector store | Databricks Vector Search |
| LLM provider | Databricks Foundation Model API |
| Default model | `databricks-claude-sonnet-4` |
| Auth | Okta OIDC (NextAuth v5) |
| Deployment | Docker Compose |
| CI/CD | GitHub Actions |
| Day-one integrations | Slack, Email (SMTP) |

Per-service configuration and env vars are documented in each service's
`.env.example` and README.

## Repository layout

```
src/UnifiedIQ-api/       FastAPI backend, catalog DDL, eval framework, tests
products/UnifiedIQ-ui/   Next.js frontend (App Router, BFF proxy)
docker-compose.yml       api + ui + optional Postgres
Makefile                 dev / test / eval / fmt / lint
.pre-commit-config.yaml  ruff, ruff-format, eslint, prettier
.github/workflows/       CI/CD (wired in a later phase)
```
