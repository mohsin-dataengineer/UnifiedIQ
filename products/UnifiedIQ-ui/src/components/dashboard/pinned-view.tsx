"use client";

import {
  Check,
  GripVertical,
  Pencil,
  RefreshCcw,
  Settings2,
  Trash2,
  X,
} from "lucide-react";
import {
  type DragEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { ResultView } from "@/components/chat/result-view";
import { useAlerts } from "@/contexts/alert-context";
import { apiPost } from "@/lib/api-client";
import type { Row, UserView, ViewLayout, ViewRunResult } from "@/lib/types";

const SIZES: Array<{ value: "S" | "M" | "L"; layout: ViewLayout }> = [
  { value: "S", layout: { w: 1, h: 1, position: 0 } },
  { value: "M", layout: { w: 2, h: 1, position: 0 } },
  { value: "L", layout: { w: 2, h: 2, position: 0 } },
];

function sizeOf(layout: ViewLayout | null | undefined): "S" | "M" | "L" {
  if (!layout) return "S";
  if (layout.w === 2 && layout.h === 2) return "L";
  if (layout.w === 2) return "M";
  return "S";
}

export interface PinnedViewHandlers {
  onUpdate: (
    id: string,
    patch: { name?: string; spec_patch?: Record<string, unknown> },
  ) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onDropOn: (sourceId: string, targetId: string) => void;
}

export function PinnedView({
  view,
  handlers,
  readOnly = false,
}: {
  view: UserView;
  handlers: PinnedViewHandlers;
  readOnly?: boolean;
}) {
  const { notify } = useAlerts();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(view.name);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [draggingOver, setDraggingOver] = useState(false);

  // Settings draft (applied with one Save click).
  const [xLabel, setXLabel] = useState(view.spec.x_label ?? "");
  const [yLabel, setYLabel] = useState(view.spec.y_label ?? "");
  const [filterText, setFilterText] = useState(view.spec.filter_text ?? "");
  const [colors, setColors] = useState<string[]>(
    view.spec.colors ?? ["#4f46e5", "#16a34a", "#ea580c"],
  );

  const nameInputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (editingName) nameInputRef.current?.focus();
  }, [editingName]);

  // Re-sync drafts when the view changes externally (e.g. server PATCH echoes back).
  useEffect(() => {
    setNameDraft(view.name);
    setXLabel(view.spec.x_label ?? "");
    setYLabel(view.spec.y_label ?? "");
    setFilterText(view.spec.filter_text ?? "");
    if (view.spec.colors && view.spec.colors.length > 0) {
      setColors(view.spec.colors);
    }
  }, [view]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiPost<ViewRunResult>(`views/${view.id}/run`, {});
      setRows(r.rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load view");
    } finally {
      setLoading(false);
    }
  }, [view.id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function commitName() {
    setEditingName(false);
    const newName = nameDraft.trim();
    if (!newName || newName === view.name) return;
    try {
      await handlers.onUpdate(view.id, { name: newName });
    } catch {
      notify("error", "Could not rename view");
    }
  }

  async function setSize(s: "S" | "M" | "L") {
    const layout = SIZES.find((x) => x.value === s)!.layout;
    const current = view.spec.layout;
    await handlers.onUpdate(view.id, {
      spec_patch: {
        layout: { ...layout, position: current?.position ?? 0 },
      },
    });
  }

  async function saveSettings() {
    await handlers.onUpdate(view.id, {
      spec_patch: {
        x_label: xLabel.trim() || null,
        y_label: yLabel.trim() || null,
        filter_text: filterText.trim() || null,
        colors: colors.filter((c) => c.trim().length > 0),
      },
    });
    setSettingsOpen(false);
    notify("success", "View updated");
  }

  function onDragStart(e: DragEvent<HTMLDivElement>) {
    if (readOnly) return;
    e.dataTransfer.setData("text/plain", view.id);
    e.dataTransfer.effectAllowed = "move";
  }
  function onDragOver(e: DragEvent<HTMLDivElement>) {
    if (readOnly) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDraggingOver(true);
  }
  function onDragLeave() {
    setDraggingOver(false);
  }
  function onDrop(e: DragEvent<HTMLDivElement>) {
    if (readOnly) return;
    e.preventDefault();
    setDraggingOver(false);
    const sourceId = e.dataTransfer.getData("text/plain");
    if (sourceId && sourceId !== view.id) {
      handlers.onDropOn(sourceId, view.id);
    }
  }

  const size = sizeOf(view.spec.layout);

  return (
    <div
      draggable={!readOnly}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={`flex h-full flex-col rounded-2xl border bg-[var(--surface)] p-4 shadow-sm transition-colors ${
        draggingOver
          ? "border-[var(--accent)] ring-2 ring-[var(--accent)]/30"
          : "border-[var(--border)]"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-1.5">
          <span
            className={`mt-0.5 text-[var(--muted)] ${
              readOnly ? "" : "cursor-grab active:cursor-grabbing"
            }`}
            title={readOnly ? "Published view" : "Drag to reorder"}
          >
            <GripVertical size={15} />
          </span>
          <div className="min-w-0">
            {editingName ? (
              <input
                ref={nameInputRef}
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                onBlur={commitName}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void commitName();
                  if (e.key === "Escape") {
                    setNameDraft(view.name);
                    setEditingName(false);
                  }
                }}
                className="w-full rounded border border-[var(--accent)] bg-[var(--surface)] px-1.5 py-0.5 text-sm font-semibold text-[var(--fg)] outline-none"
              />
            ) : (
              <button
                type="button"
                onClick={() => {
                  if (readOnly) return;
                  setNameDraft(view.name);
                  setEditingName(true);
                }}
                className={`group flex items-center gap-1 text-left text-sm font-semibold text-[var(--fg)] ${
                  readOnly ? "cursor-default" : "hover:text-[var(--accent)]"
                }`}
                title={readOnly ? "Published view" : "Rename"}
              >
                <span className="truncate">{view.name}</span>
                {!readOnly && (
                  <Pencil
                    size={11}
                    className="opacity-0 group-hover:opacity-100"
                  />
                )}
              </button>
            )}
            <p className="mt-0.5 truncate text-[11px] text-[var(--muted)]">
              {view.spec.question}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {!readOnly &&
            SIZES.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => void setSize(s.value)}
                className={`h-6 w-6 rounded-md text-[10px] font-semibold transition-colors ${
                  size === s.value
                    ? "bg-[var(--accent)] text-white"
                    : "text-[var(--muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]"
                }`}
                title={`Resize: ${s.value}`}
              >
                {s.value}
              </button>
            ))}
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="rounded-md p-1.5 text-[var(--muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)] disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCcw size={14} className={loading ? "uiq-pulse" : ""} />
          </button>
          {!readOnly && (
            <>
              <button
                type="button"
                onClick={() => setSettingsOpen((v) => !v)}
                className={`rounded-md p-1.5 hover:bg-[var(--bg)] ${
                  settingsOpen
                    ? "text-[var(--accent)]"
                    : "text-[var(--muted)] hover:text-[var(--fg)]"
                }`}
                title="Customize"
              >
                <Settings2 size={14} />
              </button>
              <button
                type="button"
                onClick={() => {
                  if (window.confirm(`Remove "${view.name}"?`)) {
                    void handlers.onDelete(view.id);
                  }
                }}
                className="rounded-md p-1.5 text-[var(--muted)] hover:bg-[var(--danger-bg)] hover:text-[var(--danger-fg)]"
                title="Remove"
              >
                <Trash2 size={14} />
              </button>
            </>
          )}
        </div>
      </div>

      {settingsOpen && !readOnly && (
        <div className="mt-3 space-y-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3">
          <div className="grid grid-cols-2 gap-2">
            <label className="text-[10px] font-medium text-[var(--muted)]">
              X axis label
              <input
                value={xLabel}
                onChange={(e) => setXLabel(e.target.value)}
                placeholder="e.g. Date"
                className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs text-[var(--fg)] outline-none focus:border-[var(--accent)]"
              />
            </label>
            <label className="text-[10px] font-medium text-[var(--muted)]">
              Y axis label
              <input
                value={yLabel}
                onChange={(e) => setYLabel(e.target.value)}
                placeholder="e.g. Revenue"
                className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs text-[var(--fg)] outline-none focus:border-[var(--accent)]"
              />
            </label>
          </div>
          <label className="block text-[10px] font-medium text-[var(--muted)]">
            Filter rows (substring across all columns)
            <input
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              placeholder="e.g. 2016-01"
              className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs text-[var(--fg)] outline-none focus:border-[var(--accent)]"
            />
          </label>
          <div>
            <p className="text-[10px] font-medium text-[var(--muted)]">
              Series colors
            </p>
            <div className="mt-1 flex gap-1.5">
              {colors.map((c, i) => (
                <input
                  key={i}
                  type="color"
                  value={c}
                  onChange={(e) =>
                    setColors((prev) =>
                      prev.map((p, idx) => (idx === i ? e.target.value : p)),
                    )
                  }
                  className="h-7 w-9 cursor-pointer rounded border border-[var(--border)] bg-transparent"
                  title={`Series ${i + 1}`}
                />
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-1.5 pt-1">
            <button
              type="button"
              onClick={() => setSettingsOpen(false)}
              className="flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--muted)] hover:text-[var(--fg)]"
            >
              <X size={11} /> Cancel
            </button>
            <button
              type="button"
              onClick={() => void saveSettings()}
              className="flex items-center gap-1 rounded-md bg-[var(--accent)] px-2 py-1 text-[11px] font-medium text-white hover:opacity-90"
            >
              <Check size={11} /> Save
            </button>
          </div>
        </div>
      )}

      <div className="mt-2 min-h-[8rem] flex-1">
        {loading && rows === null ? (
          <p className="text-xs text-[var(--muted)]">Loading…</p>
        ) : error ? (
          <p className="rounded-md bg-[var(--danger-bg)] px-3 py-2 text-xs text-[var(--danger-fg)]">
            {error}
          </p>
        ) : rows ? (
          <ResultView
            spec={view.spec.chart_config ?? undefined}
            data={rows}
            colors={view.spec.colors}
            xLabel={view.spec.x_label}
            yLabel={view.spec.y_label}
            filterText={view.spec.filter_text}
          />
        ) : null}
      </div>
    </div>
  );
}
