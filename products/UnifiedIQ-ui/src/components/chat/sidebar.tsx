"use client";

import {
  BarChart3,
  FileCheck2,
  Layers,
  MessageSquare,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";
import Link from "next/link";

import { MemoryPanel } from "@/components/chat/memory-panel";
import { useConversation } from "@/contexts/conversation-context";
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
  const { sessions, activeSessionId, switchTo, deleteChat } = useConversation();
  // Most-recently-updated first.
  const ordered = [...sessions].sort(
    (a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at),
  );

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

      <div className="mt-3 grid grid-cols-2 gap-2">
        <Link
          href="/dashboard?tab=canvas"
          className="flex items-center justify-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-2 text-xs font-medium text-[var(--fg)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
        >
          <Layers size={13} /> Canvas
        </Link>
        <Link
          href="/dashboard?tab=published"
          className="flex items-center justify-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-2 text-xs font-medium text-[var(--fg)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
        >
          <FileCheck2 size={13} /> Published
        </Link>
      </div>

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

        <div className="mt-6 flex items-center gap-1.5 px-1 text-[11px] font-semibold tracking-wide text-[var(--muted)] uppercase">
          <MessageSquare size={12} /> Recent chats
        </div>
        <div className="mt-2 space-y-1">
          {ordered.length === 0 ||
          (ordered.length === 1 && ordered[0].turns.length === 0) ? (
            <p className="px-1 text-[11px] text-[var(--muted)]">
              No saved chats yet.
            </p>
          ) : (
            ordered.map((s) => {
              const isActive = s.id === activeSessionId;
              const turnCount = s.turns.length;
              return (
                <div
                  key={s.id}
                  className={`group flex items-center gap-1 rounded-lg border px-2 py-1.5 text-xs transition-colors ${
                    isActive
                      ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                      : "border-transparent hover:border-[var(--border)] hover:bg-[var(--bg)] text-[var(--fg)]"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => switchTo(s.id)}
                    className="min-w-0 flex-1 truncate text-left"
                    title={s.title}
                  >
                    {s.title || "Untitled"}
                    {turnCount === 0 && (
                      <span className="ml-1 text-[var(--muted)]">· empty</span>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (
                        turnCount === 0 ||
                        window.confirm(`Delete "${s.title}"?`)
                      ) {
                        deleteChat(s.id);
                      }
                    }}
                    className="rounded p-0.5 text-[var(--muted)] opacity-0 transition-opacity group-hover:opacity-100 hover:text-[var(--danger-fg)]"
                    title="Delete chat"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              );
            })
          )}
        </div>

        <MemoryPanel />
      </div>

      <div className="mt-auto truncate px-1 pt-4 text-[11px] text-[var(--muted)]">
        {email}
      </div>
    </aside>
  );
}
