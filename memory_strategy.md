# Memory strategy

This document captures UnifiedIQ's memory roadmap — what it remembers
today, what it should remember next, and the design we'll follow for each
layer. It is meant as a living plan; update the **Status** column as
layers ship.

## Current state

Today the only memory we have is:

- **Per-turn history** — the chat router sends the prior turns of the
  active session as `history: ChatMessage[]` so the model has short-term
  conversational coherence.
- **Multi-session local history** — sessions are persisted in
  `localStorage` keyed by `user_email`; the user can switch between past
  threads (`ChatSession` in
  [conversation-context.tsx](products/UnifiedIQ-ui/src/contexts/conversation-context.tsx)).

What's missing:

- The model invents table/column names because it doesn't know the warehouse.
- Long sessions blow up token usage and lose focus.
- Switching threads means starting from scratch — durable user facts and
  preferences aren't carried.
- No cross-session episodic recall ("you asked something similar last week").
- Repeated identical queries hit the warehouse every time.

## Layered plan

| Tier | Layer                  | Solves                                                 | Status         |
|------|------------------------|--------------------------------------------------------|----------------|
| 1    | Schema awareness       | Stops the model inventing table/column names           | **Shipped**    |
| 2    | Result cache           | Repeated identical queries skip the warehouse          | Planned        |
| 3    | Rolling session summary| Long threads stay within budget and on topic           | Planned        |
| 4    | User memory (facts)    | Persistent cross-session user-level context            | **Shipped**    |
| 5    | Episodic recall        | "You asked something similar before" via vector store  | Future         |

## Tier 1 — Schema awareness

**Goal.** On every chat turn, inject a compact, structured description of
the tables and columns the warehouse actually contains, so generated SQL
references real names instead of hallucinated ones.

**Design.**

- `SchemaService` queries `information_schema.columns` for each
  `<catalog>.<schema>` configured in `SCHEMA_SOURCES`
  (default `workspace.default,samples.nyctaxi`).
- Results are cached in `CacheService` with TTL `SCHEMA_TTL_SECONDS`
  (default 3600).
- `SCHEMA_MAX_TABLES_INJECTED` (default 30) caps how many tables we put
  into the prompt; the chat router does a cheap keyword filter from the
  user question + recent history before selecting which tables to include.
- The chat router builds the system message as
  `SQL_GENERATION_SYSTEM + "\n\n## Available tables\n<formatted block>"`.

**Failure modes.**

- A configured source lacks `information_schema` — caught and skipped;
  other sources still load.
- All sources fail — chat still works; we just don't inject schema (the
  model falls back to its existing guesswork).
- Schema is huge — keyword filter + table cap keep the prompt bounded.

**Trade-offs.** Adds a few hundred prompt tokens per turn and one cached
warehouse query per `SCHEMA_TTL_SECONDS`. Reward: text-to-SQL goes from
"guessy" to "grounded."

## Tier 2 — Result cache (planned)

Wire the existing `CacheService` (TTLCache) into `WarehouseService.execute`:
key by normalized SQL string + first chars of the user email, value =
rows, TTL ~60s. Cuts cost and latency when the user clicks Refresh /
Re-verify / re-runs identical questions. Negligible code change; small
staleness window to document.

## Tier 3 — Rolling session summary (planned)

When a session crosses ~12 turns or ~6k tokens, replace the oldest half
with one synthesized `[SUMMARY] ...` message produced by a structured
LLM call (same `instructor` + Pydantic pattern). Always keep the last 4–6
turns verbatim. Summary itself can be re-summarized incrementally so it
doesn't grow unbounded. Extra LLM call only when threshold is crossed.

## Tier 4 — User memory (facts)

**Goal.** Persistent, cross-session "things to remember about me" — fiscal
year, default currency, naming conventions for the analyst's tables, etc.

**Design.**

- Delta table `<WAREHOUSE_CATALOG>.<WAREHOUSE_SCHEMA>.user_memory`
  (same persistence pattern as alerts and views; ensured at lifespan with
  idempotent `CREATE TABLE IF NOT EXISTS`).
- `UserMemoryService` handles CRUD; rows carry `user_email` (Principle 7).
- Router: `GET /api/memory`, `POST /api/memory`, `DELETE /api/memory/{id}`.
- Sidebar **Memory** panel for add/list/delete (mirrors the AlertsPanel
  layout).
- Chat router fetches the caller's memory and injects it as
  `"## User context\n- fact 1\n- fact 2"` before the user's question.
- Manual-add only in v1; auto-extraction (one-click "Remember this?"
  suggestions in the reasoning trail) is a follow-up.

**Trade-offs.** One small SELECT per chat turn (a few rows per user).
Privacy: every row carries `user_email`; delete-by-user wipes the user's
memory.

## Tier 5 — Episodic recall (future)

Embed each completed Q+A turn and store in a Databricks Vector Search
index keyed by `user_email`. On a new question, retrieve top-K similar
past turns from the same user and inject `"Previously you asked X and we
ran Y → result Z."` Builds on Tier 1/4 and should only be pursued once we
have real usage to learn from.

## Cross-cutting (apply to every tier as it ships)

- **Per-user scoping.** Every memory artifact carries `user_email`; row
  filters and deletes are scoped accordingly.
- **Token-budget caps.** Each injection is bounded:
  schema ≤ 800 tokens, summary ≤ 400, user memory ≤ 200, episodic ≤ 600.
- **Auditability.** Reasoning-trail `thinking` events can include which
  memories were used (e.g. `"schema: workspace.analytics.sales"`,
  `"memory: fiscal year starts in April"`).
- **Inspector + delete UI.** A single "Memory" page where every layer's
  current contents are visible and per-item deletable.
- **Right-to-forget.** Every layer supports a per-user wipe.

## Shipping cadence

1. **Tier 1 + Tier 4 (this drop).** Biggest single quality win (schema
   grounding) + the most user-visible "this thing remembers me" feature.
2. **Tier 2 + Tier 3.** Cost + token efficiency once usage warrants it.
3. **Tier 5.** Only after Tier 1–4 are validated in real use.

## Files added in this drop

- Backend
  - [src/UnifiedIQ-api/app/services/schema.py](src/UnifiedIQ-api/app/services/schema.py) — Tier 1
  - [src/UnifiedIQ-api/app/services/user_memory.py](src/UnifiedIQ-api/app/services/user_memory.py) — Tier 4
  - [src/UnifiedIQ-api/app/routers/memory.py](src/UnifiedIQ-api/app/routers/memory.py)
  - [src/UnifiedIQ-api/catalog/ddl/user_memory.sql](src/UnifiedIQ-api/catalog/ddl/user_memory.sql)
  - Settings additions in `app/config.py`
  - Chat router (`app/routers/chat.py`) builds the system message from
    base prompt + schema block + user-memory block.
- Frontend
  - `src/components/chat/memory-panel.tsx` (sidebar panel)
  - `src/lib/types.ts` adds `UserMemory`
