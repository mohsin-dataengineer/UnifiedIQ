# Conversational BI

The chat experience is the front door of UnifiedIQ. Type a question in plain
English; the model plans a query against your Databricks SQL warehouse, the
results stream back as KPI cards / a table / a chart of your choice, and the
generated SQL plus the assistant's reasoning are one click away. Anything
you produce can be pinned to a durable dashboard
(see [Dashboard.md](Dashboard.md)) or turned into an always-on alert.

## Anatomy of the chat page

| Region          | What it offers                                                                 |
|-----------------|---------------------------------------------------------------------------------|
| Left sidebar    | Brand, `New chat`, `Dashboard` link, "Try asking" suggestions, Alerts panel    |
| Top header      | Page title + subtitle + notifications bell                                     |
| Conversation    | Streaming message thread (your bubbles right-aligned, assistant cards full-width) |
| Input bar       | Auto-sizing textarea with Send / Stop (Enter to send, Shift+Enter for newline) |

## Asking a question

Every question goes through the streaming endpoint `POST /api/chat/stream`.
The backend uses `instructor` to compile the model's response into a
validated `SQLGenerationResponse` — the assistant must pick one of four
intents:

| Intent     | What happens                                                       |
|------------|--------------------------------------------------------------------|
| `data`     | Reads-only `SELECT` is run on the warehouse; rows + summary stream back |
| `chart`    | Same as `data`, plus a chart spec the UI uses as the default view |
| `clarify`  | Assistant asks a follow-up question instead of guessing            |
| `reject`   | Out-of-scope / unsafe — the assistant explains why                 |

The fixed SSE event vocabulary you'll see in the conversation:
`thinking -> sql -> chart -> data ... -> done` (and a terminal `error` if
anything goes wrong — the stream never half-closes).

## The result card

Every data answer renders one **Result card**. The same component is used
on the dashboard too, so what you see in chat is exactly what you can pin.

- **View switcher** — Segmented control to flip between **Table**, **Bar**,
  **Line**, **Area**, **Pie**. Pie is enabled only for single-series results.
  Single-row answers automatically render as a **KPI card** (big number, no
  switcher).
- **Row counter** — `N rows`, updates live when a filter is applied
  (`12 rows of 60 filtered`).
- **CSV export** — one-click download of the rendered rows.
- **Pin** — see [Dashboard.md](Dashboard.md).
- **Verify** — runs the self-audit flow: asks the LLM for a structurally
  different alternative SQL, executes both queries, and reports
  `agree` / `disagree` / `inconclusive` with a confidence pill, the
  relative difference, the two values side-by-side, and the alternative
  SQL in a collapsible. **Re-verify** is available inline. See §4.4 of
  [Architecture.md](Architecture.md) for the sequence.
- **Generated SQL** — collapsible block showing the exact SQL the model
  produced, plus any assumptions it stated (e.g. "assumed current fiscal
  year").
- **Reasoning trail** — collapsible list of the assistant's planning steps
  (`plan -> query -> summarize`). Pulses while the answer is streaming.
- **Streaming narrative** — markdown answer rendered with `react-markdown`,
  appended token-by-token as the model writes.

## Suggested questions

The sidebar ships with a few starter prompts that target
`samples.nyctaxi.trips` — every Databricks workspace has that table, so
clicking one returns real data on first try:

- *"How many trips are in samples.nyctaxi.trips?"*
- *"Average fare amount by passenger count in samples.nyctaxi.trips"*
- *"Trip count by pickup zip in samples.nyctaxi.trips as a bar chart"*
- *"Total fare revenue over time in samples.nyctaxi.trips"*

The empty state also renders the same prompts as chips. Clicking a
suggestion sends the chat immediately.

## Multi-session history (Recent chats)

- Every conversation is one `ChatSession` with an auto-derived title
  (the first user message, ≤60 chars). Sessions are stored under
  `unifiediq:sessions:{user_email}` in `localStorage`.
- **New chat** in the sidebar creates a new session and switches to it —
  the previous thread is preserved, not wiped. If the current session is
  already empty, *New chat* simply reuses it.
- **Recent chats** in the sidebar lists every saved session, most
  recently updated first. Click a row to switch threads instantly
  (charts, generated SQL, and the Verify panel all reload with the
  thread). Hover reveals a trash icon → confirmation → delete. The last
  remaining chat always survives (we recreate a fresh empty one).
- One-time migration imports any pre-existing single-thread storage into
  a session so no historical conversation is lost.
- Saved alerts, pinned views, notifications, and user memory are
  **outside** the chat session list and are never touched by these
  controls.

## User memory (persistent across every chat)

The sidebar **Memory** panel manages facts the assistant should keep in
mind on every turn ("Our fiscal year starts in April", "Default currency
USD", "Use `unifiediq.sales.fact_revenue` for revenue"). They are stored
in the `workspace.default.user_memory` Delta table keyed by
`user_email`, exposed via `GET/POST/DELETE /api/memory`, and injected
into the planner system prompt as a bullet list before every
chat. See [memory_strategy.md](memory_strategy.md) (Tier 4) for the
roadmap and Tier 1 (schema grounding) which works alongside it.
- The model only sees the messages from the current thread.

## Stop & errors

- **Stop** (the square button while streaming) calls `AbortController.abort()`
  on the SSE fetch, which the backend treats as a normal cancel.
- If anything fails (warehouse error, invalid SQL, LLM hiccup), the stream
  ends with an `error` event carrying a stable code
  (`LLM_INVALID_OUTPUT`, `SQL_INVALID`, `WAREHOUSE_ERROR`, etc.). The
  failing assistant turn shows a red error chip, and a toast appears in the
  bottom-center. Toasts auto-dismiss after 5 seconds.

## Alerts (the "always-on analyst")

The sidebar's **Alerts** panel turns any monitorable question into an alert
that fires once when a threshold is crossed.

Form fields:

| Field         | What it does                                                                 |
|---------------|------------------------------------------------------------------------------|
| Description   | "Alert me when ..." — the model compiles this into a `metric_sql` + comparator + threshold |
| Run at        | `datetime-local` picker. The alert fires once at/after this UTC time, then auto-disables |
| Channel       | **Email** or **Slack** (the in-app bell always also receives a copy)        |
| Recipient     | `you@company.com` (Email) or `#alerts` / `@user` (Slack)                    |

Validation rules (in [routers/alerts.py](src/UnifiedIQ-api/app/routers/alerts.py)):

- Recipient required when channel is Email or Slack.
- Email must match `local@domain.tld`.
- Slack recipient must start with `#` or `@`.
- The compiled `metric_sql` must parse as Databricks SQL.

### Alert lifecycle

- Saved to `workspace.default.unifiediq_alerts` (Delta), one row per alert
  (carries `user_email`).
- The in-process scheduler wakes every `ALERTS_POLL_INTERVAL_SECONDS`
  (default 300). When zero alerts exist for the workspace, it skips the
  warehouse poll entirely — no compute cost while idle.
- When a one-shot alert's `scheduled_at` passes, the scheduler evaluates the
  metric, fires through the configured channel + the in-app bell, then sets
  `enabled = false` (one-shot). Subsequent ticks skip it.
- Each alert card shows its state badge (`pending` / `ok` / `breached` /
  `error`), comparator + threshold, schedule, and channel/recipient.

### Per-alert controls

- **Run now** — evaluate immediately. Useful for proving an alert works
  without waiting for the schedule.
- **Delete** — removes the row and purges its in-app notifications so the
  bell doesn't keep showing stale fires.

### Notifications bell (header)

Polls `GET /api/notifications` every 20 seconds. Shows an unread badge.
Opening it marks them read. Each notification belongs to an alert; when you
delete an alert, its notifications are cleared automatically.

### Delivery caveats

- Slack delivery requires `SLACK_BOT_TOKEN` in the secret scope.
- Email delivery requires `SMTP_HOST` (and usually `SMTP_USERNAME` /
  `SMTP_PASSWORD`) in the secret scope.
- If neither is configured, the alert still runs and still surfaces in the
  in-app bell; only external delivery is skipped (logged, not surfaced).

## Identity & privacy

The chat page calls `GET /api/me` on mount to display your email in the
header. Identity comes from the backend's `AUTH_MODE`:

- On a Databricks App: `X-Forwarded-Email` injected by the platform after SSO.
- Local dev: `AUTH_BYPASS=true` returns a synthetic `dev@localhost`.
- Okta deployments: the `Authorization: Bearer` JWT subject.

`localStorage` keys the conversation by this email, so multiple users on the
same browser see only their own history.

## Where things live

| Concern                | File / module                                                  |
|------------------------|-----------------------------------------------------------------|
| Chat page              | [products/UnifiedIQ-ui/src/app/chat/page.tsx](products/UnifiedIQ-ui/src/app/chat/page.tsx) |
| Chat panel + input     | [components/chat/chat-panel.tsx](products/UnifiedIQ-ui/src/components/chat/chat-panel.tsx) |
| Result card            | [components/chat/result-view.tsx](products/UnifiedIQ-ui/src/components/chat/result-view.tsx) |
| Verify panel           | [components/chat/verify-panel.tsx](products/UnifiedIQ-ui/src/components/chat/verify-panel.tsx) |
| Sidebar (Recent chats / Memory / Alerts) | [components/chat/sidebar.tsx](products/UnifiedIQ-ui/src/components/chat/sidebar.tsx) |
| Memory panel           | [components/chat/memory-panel.tsx](products/UnifiedIQ-ui/src/components/chat/memory-panel.tsx) |
| Multi-session context  | [contexts/conversation-context.tsx](products/UnifiedIQ-ui/src/contexts/conversation-context.tsx) |
| SSE event reader       | [lib/sse.ts](products/UnifiedIQ-ui/src/lib/sse.ts)             |
| Streaming endpoint     | [app/routers/chat.py](src/UnifiedIQ-api/app/routers/chat.py)   |
| Verify endpoint        | [app/routers/verify.py](src/UnifiedIQ-api/app/routers/verify.py) |
| Memory endpoint        | [app/routers/memory.py](src/UnifiedIQ-api/app/routers/memory.py) |
| Verifier service       | [app/services/verifier.py](src/UnifiedIQ-api/app/services/verifier.py) |
| Schema grounding (Tier 1) | [app/services/schema.py](src/UnifiedIQ-api/app/services/schema.py) |
| User memory (Tier 4)   | [app/services/user_memory.py](src/UnifiedIQ-api/app/services/user_memory.py) |
| Structured planner     | [app/prompts/chat_system.py](src/UnifiedIQ-api/app/prompts/chat_system.py) + [app/models/responses.py](src/UnifiedIQ-api/app/models/responses.py) |
| Alerts                 | [app/services/alerts.py](src/UnifiedIQ-api/app/services/alerts.py) + [components/chat/alerts-panel.tsx](products/UnifiedIQ-ui/src/components/chat/alerts-panel.tsx) |
