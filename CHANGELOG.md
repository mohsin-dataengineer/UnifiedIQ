# Changelog

A chronological log of feature drops in this build of UnifiedIQ.
Entries are most-recent-first and use [Keep-a-Changelog](https://keepachangelog.com/)
style categories. Versions are *milestone tags* rather than semver
releases; this build pre-dates a formal version cut.

## [Unreleased] — memory + trust + history

### Added

- **User memory (Memory · Tier 4).** New Delta table `user_memory` plus
  `GET/POST/DELETE /api/memory`, a sidebar Memory panel, and prompt
  injection. The chat router prepends an `"## User context"` bullet list
  to the planner system message on every turn. (See
  [memory_strategy.md](memory_strategy.md).)
- **Schema grounding (Memory · Tier 1).** New `SchemaService` queries
  `<catalog>.information_schema.columns` for each `SCHEMA_SOURCES`
  entry, caches the result, keyword-ranks tables against the user's
  question, and renders an `"## Available tables"` block injected into
  the planner system message. Default sources: `workspace.default` and
  `samples.nyctaxi`.
- **Multi-session chat history.** `ConversationContext` now manages a
  list of `ChatSession`s with an active session at a time, persisted
  under `unifiediq:sessions:{user_email}` in `localStorage`. Sidebar
  *Recent chats* lists every saved thread; *New chat* preserves the
  prior conversation. One-time migration from the legacy single-thread
  key.
- **Self-auditing answers.** New `POST /api/chat/verify`, a
  `VerifierService` that asks the LLM for a structurally different
  alternative SQL, runs both queries, compares numerics within tolerance
  bands (1% / 5% / 20%), and falls back to a reusable `llm_judge` for
  non-scalar comparisons. A **Verify** button + result panel on every
  chat result card.
- **Dashboard editor controls.** Each pinned card now supports inline
  rename, S/M/L resize (grid spans), drag-and-drop reorder (HTML5
  native), and a settings popover with X/Y axis labels, custom series
  colors, and a substring row filter. Layout, colors, labels, and
  filter are persisted in `user_views.spec` JSON via
  `PATCH /api/views/{id}`.
- **Pin-to-dashboard.** Pin any chat result to a `/dashboard` page that
  re-runs the saved SQL on load. New `user_views` Delta table +
  `GET/POST/DELETE/PATCH /api/views` + `POST /api/views/{id}/run`.
- **Natural-language alerts.** `unifiediq_alerts` Delta table, the
  `AlertService` + in-process `AlertScheduler`, a sidebar Alerts panel
  with description / `datetime-local` schedule / channel (Email or Slack)
  / recipient, and a header notifications bell with auto-clear on alert
  delete. One-shot scheduled alerts auto-disable after firing. The
  scheduler skips the warehouse poll entirely when zero alerts are
  active so the SQL warehouse can auto-suspend.
- **Conversational-BI redesign.** A unified card-based result view with
  KPI / Table / Bar / Line / Area / Pie switcher, CSV export, and the
  Pin / Verify / segmented control toolbar. Sidebar suggestions are
  tailored to `samples.nyctaxi.trips`.
- **System-context diagram.** Hand-authored
  [assets/architecture.svg](assets/architecture.svg) in the
  three-column "user devices / application layer / external services"
  style, plus Mermaid sequence/ER/CI diagrams for the technical flows
  in [Architecture.md](Architecture.md).

### Changed

- **LLM provider hardening.** Default model is
  `databricks-meta-llama-3-3-70b-instruct`; `instructor` mode is
  `MD_JSON` (Databricks rejects `response_format=json_object` for these
  endpoints). Reasoning models (`gpt-oss-*`) are explicitly avoided —
  their parts-list `message.content` breaks structured parsing.
- **Auth modes.** `AUTH_MODE` selects between `oidc` (Okta JWT),
  `databricks` (trusts `X-Forwarded-*` after platform SSO), and
  `bypass`. `AUTH_BYPASS=true` overrides for local dev. The deployed
  app reads identity from forwarded headers only.
- **Persistence schema.** Warehouse catalog/schema defaults moved from
  `main.analytics` (does not exist in trial workspaces) to
  `workspace.default`. Delta tables (`unifiediq_alerts`, `user_views`,
  `user_memory`) are ensured at lifespan with idempotent `ALTER TABLE
  ADD COLUMNS` migrations.
- **Deployment shape.** Production now runs as a **single Databricks
  App**: FastAPI serves both `/api/*` and a prebuilt Next.js static
  bundle out of `src/UnifiedIQ-api/static/`. The Next.js BFF /
  NextAuth tier is retained only in the local Docker Compose path.
- **Toasts auto-dismiss** after 5 seconds; bell notifications clear
  automatically when their parent alert is deleted.

### Documentation

- New top-level docs:
  [README.md](README.md),
  [Architecture.md](Architecture.md),
  [ConversationalBI.md](ConversationalBI.md),
  [Dashboard.md](Dashboard.md),
  [memory_strategy.md](memory_strategy.md),
  [CLAUDE.md](CLAUDE.md),
  and this `CHANGELOG.md`.

## Initial scaffold

The phased build followed the brief at `Part 1–8`: repo skeleton,
backend foundation (config / services / models / prompts / workers /
error model), frontend foundation, streaming chat flow, eval framework,
integration framework, CI/CD + pre-commit, and final acceptance pass.
See git history (`git log --oneline`) for per-commit detail.
