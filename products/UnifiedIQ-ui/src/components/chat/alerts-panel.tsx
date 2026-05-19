"use client";

import { Bell, Play, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useAlerts } from "@/contexts/alert-context";
import { apiDelete, ApiError, apiGet, apiPost } from "@/lib/api-client";
import type { Alert } from "@/lib/types";

const STATE_STYLE: Record<string, string> = {
  pending: "bg-neutral-100 text-neutral-600",
  ok: "bg-green-100 text-green-700",
  breached: "bg-red-100 text-red-700",
  error: "bg-amber-100 text-amber-700",
};

export function AlertsPanel() {
  const { notify } = useAlerts();
  const [alerts, setAlertList] = useState<Alert[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setAlertList(await apiGet<Alert[]>("alerts"));
    } catch {
      // listing unavailable (e.g. warehouse offline) — leave empty
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function create() {
    const question = q.trim();
    if (!question || busy) return;
    setBusy(true);
    try {
      await apiPost<Alert>("alerts", { question });
      setQ("");
      notify("success", "Alert created");
      await refresh();
    } catch (e) {
      notify(
        "error",
        e instanceof ApiError ? e.message : "Could not create alert",
      );
    } finally {
      setBusy(false);
    }
  }

  async function run(id: string) {
    try {
      await apiPost(`alerts/${id}/run`, {});
      notify("info", "Alert evaluated");
      await refresh();
    } catch {
      notify("error", "Run failed");
    }
  }

  async function remove(id: string) {
    try {
      await apiDelete(`alerts/${id}`);
      await refresh();
    } catch {
      notify("error", "Delete failed");
    }
  }

  return (
    <div className="mt-6">
      <div className="flex items-center gap-1.5 px-1 text-[11px] font-semibold tracking-wide text-[var(--muted)] uppercase">
        <Bell size={12} /> Alerts
      </div>

      <div className="mt-2 flex gap-1.5">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void create()}
          placeholder="Alert me when…"
          className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-xs outline-none focus:border-[var(--accent)]"
        />
        <button
          type="button"
          onClick={() => void create()}
          disabled={busy || !q.trim()}
          className="rounded-lg bg-[var(--accent)] px-2.5 py-1.5 text-xs font-medium text-white disabled:opacity-40"
        >
          Add
        </button>
      </div>

      <div className="mt-3 space-y-2">
        {alerts.length === 0 ? (
          <p className="px-1 text-[11px] text-[var(--muted)]">
            No alerts yet. e.g. “ping me when trip count in
            samples.nyctaxi.trips exceeds 20000”.
          </p>
        ) : (
          alerts.map((a) => (
            <div
              key={a.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2.5"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-medium text-[var(--fg)]">
                  {a.title}
                </span>
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${STATE_STYLE[a.last_state]}`}
                >
                  {a.last_state}
                  {a.last_value != null ? ` · ${a.last_value}` : ""}
                </span>
              </div>
              <div className="mt-1 text-[11px] text-[var(--muted)]">
                {a.comparator} {a.threshold} · every {a.cadence_minutes}m ·{" "}
                {a.channel}
              </div>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => void run(a.id)}
                  className="flex items-center gap-1 text-[11px] text-[var(--muted)] hover:text-[var(--accent)]"
                >
                  <Play size={11} /> Run now
                </button>
                <button
                  type="button"
                  onClick={() => void remove(a.id)}
                  className="flex items-center gap-1 text-[11px] text-[var(--muted)] hover:text-red-600"
                >
                  <Trash2 size={11} /> Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
