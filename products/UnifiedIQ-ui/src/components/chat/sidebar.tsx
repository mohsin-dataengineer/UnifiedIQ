"use client";

import { BarChart3, Plus, Sparkles } from "lucide-react";

import { AlertsPanel } from "@/components/chat/alerts-panel";
import { appName } from "@/lib/env";

export const SUGGESTIONS = [
  "How many trips are in samples.nyctaxi.trips?",
  "Average fare amount by passenger count in samples.nyctaxi.trips",
  "Trip count by pickup zip in samples.nyctaxi.trips as a bar chart",
  "Total fare revenue over time in samples.nyctaxi.trips",
];

export function Sidebar({
  email,
  onNewChat,
  onPick,
}: {
  email: string;
  onNewChat: () => void;
  onPick: (q: string) => void;
}) {
  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex items-center gap-2 px-1">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
          <BarChart3 size={17} />
        </div>
        <div>
          <div className="text-sm font-semibold text-[var(--fg)]">
            {appName}
          </div>
          <div className="text-[11px] text-[var(--muted)]">
            Conversational BI
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={onNewChat}
        className="mt-5 flex items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
      >
        <Plus size={15} /> New chat
      </button>

      <div className="mt-4 flex-1 overflow-y-auto pr-1">
        <div className="px-1 text-[11px] font-semibold tracking-wide text-[var(--muted)] uppercase">
          Try asking
        </div>
        <div className="mt-2 space-y-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onPick(s)}
              className="flex w-full items-start gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-left text-xs text-[var(--fg)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
            >
              <Sparkles size={13} className="mt-0.5 shrink-0" />
              {s}
            </button>
          ))}
        </div>

        <AlertsPanel />
      </div>

      <div className="mt-auto truncate px-1 pt-4 text-[11px] text-[var(--muted)]">
        {email}
      </div>
    </aside>
  );
}
