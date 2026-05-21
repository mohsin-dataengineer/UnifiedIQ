"use client";

import {
  ArrowLeft,
  Bell,
  ChevronDown,
  FileCheck2,
  Layers,
  LayoutDashboard,
  Pencil,
  Plus,
  RefreshCcw,
  Rocket,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AlertsPanel } from "@/components/chat/alerts-panel";
import { PinnedView } from "@/components/dashboard/pinned-view";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useAlerts } from "@/contexts/alert-context";
import { useCanvasWorkspace } from "@/contexts/canvas-workspace-context";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { appName } from "@/lib/env";
import type { Canvas, UserView, ViewLayout } from "@/lib/types";

type Tab = "canvas" | "published";

function ensureLayout(v: UserView, fallbackPosition: number): ViewLayout {
  const l = v.spec.layout;
  return {
    w: (l?.w as 1 | 2) ?? 1,
    h: (l?.h as 1 | 2) ?? 1,
    position: typeof l?.position === "number" ? l.position : fallbackPosition,
  };
}

function sortByPosition(views: UserView[]): UserView[] {
  return [...views].sort((a, b) => {
    const ap = a.spec.layout?.position ?? 0;
    const bp = b.spec.layout?.position ?? 0;
    return ap - bp;
  });
}

function sortCanvases(canvases: Canvas[]): Canvas[] {
  return [...canvases].sort(
    (a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at),
  );
}

export function CanvasDashboardWorkspace() {
  const { notify } = useAlerts();
  const {
    activeDraftCanvasId,
    setActiveDraftCanvasId,
    version,
    notifyWorkspaceChanged,
  } = useCanvasWorkspace();
  const [tab, setTab] = useState<Tab>("canvas");
  const [canvases, setCanvases] = useState<Canvas[]>([]);
  const [activePublishedId, setActivePublishedId] = useState<string | null>(
    null,
  );
  const [views, setViews] = useState<UserView[] | null>(null);
  const [loadingCanvases, setLoadingCanvases] = useState(true);
  const [alertsOpen, setAlertsOpen] = useState(false);

  const drafts = useMemo(
    () => sortCanvases(canvases.filter((c) => c.status === "draft")),
    [canvases],
  );
  const published = useMemo(
    () => sortCanvases(canvases.filter((c) => c.status === "published")),
    [canvases],
  );

  const activeCanvasId =
    tab === "canvas" ? activeDraftCanvasId : activePublishedId;
  const activeCanvas = canvases.find((c) => c.id === activeCanvasId) ?? null;
  const readOnly = activeCanvas?.status === "published";

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    setTab(params.get("tab") === "published" ? "published" : "canvas");
  }, []);

  function selectTab(next: Tab) {
    setTab(next);
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    url.searchParams.set("tab", next);
    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }

  const refreshCanvases = useCallback(async () => {
    setLoadingCanvases(true);
    try {
      const list = sortCanvases(await apiGet<Canvas[]>("canvases"));
      setCanvases(list);
      const nextDrafts = list.filter((c) => c.status === "draft");
      const nextPublished = list.filter((c) => c.status === "published");
      setActiveDraftCanvasId((current) =>
        current && nextDrafts.some((c) => c.id === current)
          ? current
          : (nextDrafts[0]?.id ?? null),
      );
      setActivePublishedId((current) =>
        current && nextPublished.some((c) => c.id === current)
          ? current
          : (nextPublished[0]?.id ?? null),
      );
    } catch {
      setCanvases([]);
    } finally {
      setLoadingCanvases(false);
    }
  }, [setActiveDraftCanvasId]);

  const refreshViews = useCallback(async () => {
    if (!activeCanvasId) {
      setViews([]);
      return;
    }
    setViews(null);
    try {
      const list = await apiGet<UserView[]>(
        `views?canvas_id=${encodeURIComponent(activeCanvasId)}`,
      );
      setViews(sortByPosition(list));
    } catch {
      setViews([]);
    }
  }, [activeCanvasId]);

  useEffect(() => {
    void refreshCanvases();
  }, [refreshCanvases, version]);

  useEffect(() => {
    void refreshViews();
  }, [refreshViews]);

  async function createCanvas() {
    const name = window.prompt("Canvas name", "New canvas")?.trim();
    if (!name) return;
    try {
      const created = await apiPost<Canvas>("canvases", { name });
      selectTab("canvas");
      setActiveDraftCanvasId(created.id);
      notify("success", "Canvas created");
      await refreshCanvases();
    } catch {
      notify("error", "Could not create canvas");
    }
  }

  async function renameCanvas() {
    if (!activeCanvas || readOnly) return;
    const name = window.prompt("Rename canvas", activeCanvas.name)?.trim();
    if (!name || name === activeCanvas.name) return;
    try {
      const updated = await apiPatch<Canvas>(`canvases/${activeCanvas.id}`, {
        name,
      });
      setCanvases((prev) =>
        prev.map((c) => (c.id === updated.id ? updated : c)),
      );
      notify("success", "Canvas renamed");
    } catch {
      notify("error", "Could not rename canvas");
      await refreshCanvases();
    }
  }

  async function deleteCanvas() {
    if (!activeCanvas || readOnly) return;
    if (!window.confirm(`Delete "${activeCanvas.name}" and its views?`)) {
      return;
    }
    try {
      await apiDelete(`canvases/${activeCanvas.id}`);
      notify("info", "Canvas deleted");
      await refreshCanvases();
      notifyWorkspaceChanged();
    } catch {
      notify("error", "Could not delete canvas");
    }
  }

  async function publishCanvas() {
    if (!activeCanvas || readOnly || !views?.length) return;
    try {
      const publishedCanvas = await apiPost<Canvas>(
        `canvases/${activeCanvas.id}/publish`,
        {},
      );
      selectTab("published");
      setActivePublishedId(publishedCanvas.id);
      notify("success", "Published dashboard created");
      await refreshCanvases();
    } catch {
      notify("error", "Could not publish canvas");
    }
  }

  async function onUpdate(
    id: string,
    patch: { name?: string; spec_patch?: Record<string, unknown> },
  ): Promise<void> {
    if (readOnly) return;
    setViews((prev) =>
      prev
        ? prev.map((v) =>
            v.id === id
              ? {
                  ...v,
                  name: patch.name ?? v.name,
                  spec: { ...v.spec, ...(patch.spec_patch ?? {}) },
                }
              : v,
          )
        : prev,
    );
    try {
      const updated = await apiPatch<UserView>(`views/${id}`, {
        name: patch.name,
        spec: patch.spec_patch,
      });
      setViews((prev) =>
        prev ? prev.map((v) => (v.id === id ? updated : v)) : prev,
      );
      notifyWorkspaceChanged();
    } catch {
      notify("error", "Could not save changes");
      await refreshViews();
    }
  }

  async function onDelete(id: string): Promise<void> {
    if (readOnly) return;
    setViews((prev) => (prev ? prev.filter((v) => v.id !== id) : prev));
    try {
      await apiDelete(`views/${id}`);
      notify("info", "Removed from canvas");
      notifyWorkspaceChanged();
    } catch {
      notify("error", "Could not remove view");
      await refreshViews();
    }
  }

  async function onDropOn(sourceId: string, targetId: string): Promise<void> {
    if (readOnly || !views) return;
    const src = views.findIndex((v) => v.id === sourceId);
    const tgt = views.findIndex((v) => v.id === targetId);
    if (src < 0 || tgt < 0) return;
    const reordered = [...views];
    const [moved] = reordered.splice(src, 1);
    reordered.splice(tgt, 0, moved);
    const withPositions = reordered.map((v, i) => ({
      ...v,
      spec: {
        ...v.spec,
        layout: { ...ensureLayout(v, i), position: i },
      },
    }));
    setViews(withPositions);
    try {
      await Promise.all(
        withPositions.map((v) =>
          apiPatch<UserView>(`views/${v.id}`, {
            spec: { layout: v.spec.layout },
          }),
        ),
      );
      notifyWorkspaceChanged();
    } catch {
      notify("error", "Could not save new order");
      await refreshViews();
    }
  }

  const choices = tab === "canvas" ? drafts : published;
  const emptyLabel =
    tab === "canvas"
      ? "No canvases yet. Create one, then pin chat results into it."
      : "No published dashboards yet. Build a canvas, then publish it.";

  const handlers = {
    onUpdate,
    onDelete,
    onDropOn: (sourceId: string, targetId: string) =>
      void onDropOn(sourceId, targetId),
  };

  return (
    <main className="flex h-screen flex-col bg-[var(--bg)]">
      <header className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-6 py-4">
        <div className="flex items-center gap-4">
          <Link
            href="/chat"
            className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-[var(--muted)] transition-colors hover:text-[var(--fg)]"
          >
            <ArrowLeft size={15} /> Back to chat
          </Link>
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
              <LayoutDashboard size={16} />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-[var(--fg)]">
                {appName} Canvas & Dashboards
              </h1>
              <p className="text-[11px] text-[var(--muted)]">
                Build drafts, then publish immutable dashboard snapshots
              </p>
            </div>
          </div>
        </div>
        <ThemeToggle />
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto max-w-7xl">
          <section className="border-b border-[var(--border)] pb-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
                  <LayoutDashboard size={16} />
                </div>
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-semibold text-[var(--fg)]">
                    Canvas & Dashboards
                  </h2>
                  <p className="truncate text-[11px] text-[var(--muted)]">
                    Build drafts, then publish immutable snapshots
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => void refreshCanvases()}
                className="rounded-md p-1.5 text-[var(--muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]"
                title="Refresh canvases"
                aria-label="Refresh canvases"
              >
                <RefreshCcw
                  size={14}
                  className={loadingCanvases ? "uiq-pulse" : ""}
                />
              </button>
            </div>

            <div className="mt-4 grid max-w-2xl grid-cols-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1">
              <button
                type="button"
                onClick={() => selectTab("canvas")}
                className={`flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold transition-colors ${
                  tab === "canvas"
                    ? "bg-[var(--accent)] text-white shadow-sm"
                    : "text-[var(--muted)] hover:text-[var(--fg)]"
                }`}
                aria-pressed={tab === "canvas"}
              >
                <Layers size={13} /> Canvas
              </button>
              <button
                type="button"
                onClick={() => selectTab("published")}
                className={`flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold transition-colors ${
                  tab === "published"
                    ? "bg-[var(--accent)] text-white shadow-sm"
                    : "text-[var(--muted)] hover:text-[var(--fg)]"
                }`}
                aria-pressed={tab === "published"}
              >
                <FileCheck2 size={13} /> Published Dashboards
              </button>
            </div>

            <div className="mt-4 flex max-w-2xl gap-2">
              <select
                value={activeCanvasId ?? ""}
                onChange={(e) => {
                  const id = e.target.value || null;
                  if (tab === "canvas") setActiveDraftCanvasId(id);
                  else setActivePublishedId(id);
                }}
                className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-2 text-xs text-[var(--fg)] outline-none focus:border-[var(--accent)]"
              >
                <option value="">{choices.length ? "Select" : "None"}</option>
                {choices.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              {tab === "canvas" && (
                <button
                  type="button"
                  onClick={() => void createCanvas()}
                  className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
                  title="New canvas"
                  aria-label="New canvas"
                >
                  <Plus size={15} />
                </button>
              )}
            </div>

            {tab === "canvas" && activeCanvas && (
              <div className="mt-3 grid max-w-2xl grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => void renameCanvas()}
                  className="flex items-center justify-center gap-1 rounded-md border border-[var(--border)] px-2 py-1.5 text-[11px] text-[var(--muted)] hover:text-[var(--fg)]"
                >
                  <Pencil size={11} /> Rename
                </button>
                <button
                  type="button"
                  onClick={() => void publishCanvas()}
                  disabled={!views?.length}
                  className="flex items-center justify-center gap-1 rounded-md bg-[var(--accent)] px-2 py-1.5 text-[11px] font-medium text-white disabled:opacity-40"
                  title={
                    views?.length
                      ? "Publish immutable dashboard"
                      : "Pin at least one view before publishing"
                  }
                >
                  <Rocket size={11} /> Publish
                </button>
                <button
                  type="button"
                  onClick={() => void deleteCanvas()}
                  className="flex items-center justify-center gap-1 rounded-md border border-[var(--danger-border)] px-2 py-1.5 text-[11px] text-[var(--danger-fg)] hover:bg-[var(--danger-bg)]"
                >
                  <Trash2 size={11} /> Delete
                </button>
              </div>
            )}
          </section>

          <section className="flex items-start gap-5 py-5">
            <div className="min-w-0 flex-1">
              {!activeCanvas ? (
                <p className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface)] px-3 py-16 text-center text-sm text-[var(--muted)]">
                  {emptyLabel}
                </p>
              ) : views === null ? (
                <p className="text-sm text-[var(--muted)]">Loading views…</p>
              ) : views.length === 0 ? (
                <p className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface)] px-3 py-16 text-center text-sm text-[var(--muted)]">
                  {tab === "canvas"
                    ? "No views in this canvas yet. Pin a result from chat to start building."
                    : "This published dashboard has no views."}
                </p>
              ) : (
                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                  {views.map((v) => {
                    const layout = ensureLayout(v, 0);
                    return (
                      <div
                        key={v.id}
                        style={{
                          gridColumn: layout.w === 2 ? "span 2" : "span 1",
                          minHeight: layout.h === 2 ? "36rem" : "22rem",
                        }}
                      >
                        <PinnedView
                          view={v}
                          handlers={handlers}
                          readOnly={readOnly}
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {tab === "published" && (
              <aside className="sticky top-5 w-80 shrink-0 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
                <button
                  type="button"
                  onClick={() => setAlertsOpen((open) => !open)}
                  className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-2 text-left text-sm font-semibold text-[var(--fg)] hover:bg-[var(--bg)]"
                  aria-expanded={alertsOpen}
                >
                  <span className="flex items-center gap-2">
                    <Bell size={14} /> Alerts
                  </span>
                  <ChevronDown
                    size={15}
                    className={`text-[var(--muted)] transition-transform ${
                      alertsOpen ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {alertsOpen ? (
                  <div className="mt-2 border-t border-[var(--border)] pt-3">
                    <AlertsPanel className="" />
                  </div>
                ) : (
                  <p className="px-2 pb-2 text-xs text-[var(--muted)]">
                    Expand to create, run, or manage published dashboard alerts.
                  </p>
                )}
              </aside>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
