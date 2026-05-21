"use client";

import { Brain, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useAlerts } from "@/contexts/alert-context";
import { apiDelete, ApiError, apiGet, apiPost } from "@/lib/api-client";
import type { UserMemory } from "@/lib/types";

export function MemoryPanel() {
  const { notify } = useAlerts();
  const [items, setItems] = useState<UserMemory[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setItems(await apiGet<UserMemory[]>("memory"));
    } catch {
      // memory unavailable; leave empty
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function add() {
    const value = draft.trim();
    if (!value || busy) return;
    setBusy(true);
    try {
      await apiPost<UserMemory>("memory", { value });
      setDraft("");
      notify("success", "Saved to memory");
      await refresh();
    } catch (e) {
      notify(
        "error",
        e instanceof ApiError ? e.message : "Could not save memory",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await apiDelete(`memory/${id}`);
      await refresh();
    } catch {
      notify("error", "Delete failed");
    }
  }

  return (
    <div className="mt-6">
      <div className="flex items-center gap-1.5 px-1 text-[11px] font-semibold tracking-wide text-[var(--muted)] uppercase">
        <Brain size={12} /> Memory
      </div>
      <p className="mt-1 px-1 text-[10px] leading-snug text-[var(--muted)]">
        Persistent facts the assistant should keep in mind across every chat.
      </p>

      <div className="mt-2 flex gap-1.5">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void add()}
          placeholder="e.g. fiscal year starts in April"
          className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-xs outline-none focus:border-[var(--accent)]"
        />
        <button
          type="button"
          onClick={() => void add()}
          disabled={busy || !draft.trim()}
          className="flex items-center gap-1 rounded-lg bg-[var(--accent)] px-2 py-1.5 text-xs font-medium text-white disabled:opacity-40"
          title="Remember this"
        >
          <Plus size={12} />
        </button>
      </div>

      <div className="mt-2 space-y-1">
        {items.length === 0 ? (
          <p className="px-1 text-[11px] text-[var(--muted)]">
            Nothing remembered yet.
          </p>
        ) : (
          items.map((m) => (
            <div
              key={m.id}
              className="group flex items-start gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5"
            >
              <span className="min-w-0 flex-1 text-xs text-[var(--fg)]">
                {m.value}
              </span>
              <button
                type="button"
                onClick={() => void remove(m.id)}
                className="rounded p-0.5 text-[var(--muted)] opacity-0 transition-opacity group-hover:opacity-100 hover:text-[var(--danger-fg)]"
                title="Forget"
              >
                <Trash2 size={11} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
