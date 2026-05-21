# Dashboard

UnifiedIQ's dashboard turns ad-hoc conversations into a durable, editable
home page. Pin any KPI or chart you get in chat, lay them out the way you
want, and they will re-execute their saved SQL every time the dashboard
loads — so the numbers stay live without you re-asking the question.

For the chat side of this experience (incl. *Verify*, *Recent chats*,
and the *Memory* panel) see [ConversationalBI.md](ConversationalBI.md).
For the persistence model and endpoints see
[Architecture.md](Architecture.md). The full memory roadmap (schema
grounding, user memory, result cache, summary, episodic recall) lives in
[memory_strategy.md](memory_strategy.md).

## Pinning a view

Every result card in chat has a **Pin** button next to **CSV** and
**Verify**. Clicking it:

1. Prompts for a name (defaulted from your question).
2. Captures the question, the generated SQL, the chart spec, and the
   currently-selected view (Table / Bar / Line / Area / Pie / KPI).
3. Posts to `POST /api/views`; the backend re-validates the SQL via
   `sqlglot.transpile(dialect="databricks")` and stores the spec as JSON in
   the Delta table `workspace.default.user_views`.
4. The button flips to "Pinned".

The view is now reachable from the **Dashboard** link in the chat sidebar.

## The dashboard layout

Routed at `/dashboard`. The page:

- Fetches the user's views on mount (`GET /api/views`).
- Sorts them by `spec.layout.position` so your ordering is preserved.
- Renders them in a responsive CSS grid (1 column on small screens,
  2 columns from `lg`).
- Each card runs its own `POST /api/views/{id}/run` on mount, so the data
  is fresh, not a snapshot.

The header has a `Back to chat` link and the same notifications bell from
the chat page.

## Per-card controls

Every card carries a toolbar in the top-right and a drag handle on the
top-left. All edits persist via `PATCH /api/views/{id}` (the backend
merges a partial spec patch and re-validates).

| Control            | What it does                                                                       |
|--------------------|------------------------------------------------------------------------------------|
| Drag handle        | Drag onto another card to reorder. Positions are persisted via parallel PATCHes.   |
| Title (click)      | Inline rename. Enter saves, Esc cancels.                                           |
| `S` / `M` / `L`    | Resize the card. `S` = half-column, `M` = full row, `L` = full row at 2x height.   |
| Refresh            | Re-runs the saved SQL right away.                                                  |
| Settings (gear)    | Opens the customization popover (below).                                           |
| Trash              | Deletes the view (with a confirm prompt).                                          |

The result body itself reuses the chat **Result card**, so the chart-type
switcher (Table / Bar / Line / Area / Pie / KPI), CSV export, generated SQL
accordion, and row counter all work the same on the dashboard.

## Customization popover

Click the gear on any card. One Save commits all four edits at once:

| Field             | Effect                                                                          |
|-------------------|---------------------------------------------------------------------------------|
| X axis label      | Stored as `spec.x_label`; Recharts renders it under the X axis.                 |
| Y axis label      | Stored as `spec.y_label`; Recharts renders it rotated alongside the Y axis.     |
| Filter rows       | Case-insensitive substring matched across every column. Row counter and exported CSV both reflect the filter. |
| Series colors     | Three color pickers. The chart palette uses these for the first three series and falls back to defaults beyond. |

Switching the view type (Table / Bar / ...) in the body persists in your
local UI session but is not saved to the spec — the saved `default_view` is
the one captured at pin time.

## Resizing

Sizes map to CSS Grid spans (rendered inline so it works inside the
two-column grid):

| Size | `layout.w` | `layout.h` | Effect                              |
|------|------------|------------|-------------------------------------|
| S    | 1          | 1          | Half column, normal height          |
| M    | 2          | 1          | Full row, normal height             |
| L    | 2          | 2          | Full row, double height (`min-height: 36rem`) |

Clicking a size button persists immediately and the grid reflows.

## Reordering

Drag-and-drop uses native HTML5 (`draggable` + `dataTransfer`):

1. Drag any card by the grip icon.
2. Hover over another card — its outline highlights.
3. Drop. The two cards swap into the new order (the source's previous slot
   becomes the target's, and the source is inserted at the target's index).
4. Every card's `spec.layout.position` is updated and PATCHed in parallel,
   so the order is durable across sessions.

Honest limit: HTML5 native drag works on desktop and works on iPadOS, but
plain mobile touch drag isn't supported. If you want this to be touch-native
we can swap in `@dnd-kit/sortable` later.

## Renaming

Click the card title to turn it into an inline input. Press Enter to save,
Esc to cancel. The change persists with a single PATCH. Hovering the title
reveals a pencil hint.

## Refresh, delete, and re-running

- **Refresh** re-executes the saved SQL and replaces the in-memory rows.
- **Delete** removes the row from `user_views` with a confirm.
- The dashboard does **not** auto-poll. Each card runs once on load; the
  refresh icon is how you pull a fresh snapshot.

## Persistence model

A pinned view in `workspace.default.user_views` is one row with:

| Column       | Notes                                                          |
|--------------|----------------------------------------------------------------|
| `view_id`    | UUID hex.                                                      |
| `user_email` | Owner (multi-tenancy by user_email — Principle 7).             |
| `name`       | User-editable.                                                 |
| `kind`       | `chart` for everything pinned from chat today.                 |
| `spec`       | JSON: `{question, sql, chart_config, default_view, filter_text, layout, colors, x_label, y_label}`. |
| `is_shared`  | Reserved for future per-view sharing.                          |
| timestamps   | `created_at`, `updated_at`.                                    |

The `spec` JSON is the single source of truth — every UI customization round-trips through the merge in `ViewsService.update`, which re-validates the merged spec before writing. New fields can be added by appending to `ViewSpec` without a schema migration.

## Empty state

If you have not pinned anything yet, the dashboard shows a one-screen
empty state with a CTA back to `/chat`. The chat page's **Dashboard** link
in the sidebar always navigates here.

## Where things live

| Concern                  | File                                                                |
|--------------------------|---------------------------------------------------------------------|
| Dashboard page           | [products/UnifiedIQ-ui/src/app/dashboard/page.tsx](products/UnifiedIQ-ui/src/app/dashboard/page.tsx) |
| Per-card component       | [components/dashboard/pinned-view.tsx](products/UnifiedIQ-ui/src/components/dashboard/pinned-view.tsx) |
| Pin button (in chat)     | [components/chat/result-view.tsx](products/UnifiedIQ-ui/src/components/chat/result-view.tsx) |
| Views service (CRUD/run) | [src/UnifiedIQ-api/app/services/views.py](src/UnifiedIQ-api/app/services/views.py) |
| Views router             | [src/UnifiedIQ-api/app/routers/views.py](src/UnifiedIQ-api/app/routers/views.py) |
| `ViewSpec` model         | [src/UnifiedIQ-api/app/models/domain.py](src/UnifiedIQ-api/app/models/domain.py) |
| Delta DDL                | [catalog/ddl/user_views.sql](src/UnifiedIQ-api/catalog/ddl/user_views.sql) |
