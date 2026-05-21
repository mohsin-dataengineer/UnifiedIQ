"use client";

import {
  Bell,
  CalendarClock,
  Mail,
  MessageSquare,
  Play,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useAlerts } from "@/contexts/alert-context";
import { apiDelete, ApiError, apiGet, apiPost } from "@/lib/api-client";
import type { Alert } from "@/lib/types";

const STATE_STYLE: Record<string, string> = {
  pending: "bg-[var(--info-bg)] text-[var(--info-fg)]",
  ok: "bg-[var(--success-bg)] text-[var(--success-fg)]",
  breached: "bg-[var(--danger-bg)] text-[var(--danger-fg)]",
  error: "bg-[var(--warning-bg)] text-[var(--warning-fg)]",
};

type Channel = "email" | "slack";

const EXAMPLES = [
  "Trip count in samples.nyctaxi.trips exceeds 20000",
  "Average fare in samples.nyctaxi.trips drops below 10",
];

// Returns "YYYY-MM-DDTHH:MM" in the user's local time for datetime-local
// input default values.
function localDatetimeInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

const DATE_FMT = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

function formatScheduled(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : DATE_FMT.format(d);
}

function defaultRunAt(): string {
  return localDatetimeInput(new Date(Date.now() + 60 * 60 * 1000));
}

export function AlertsPanel({
  className = "mt-6",
}: { className?: string } = {}) {
  const { notify } = useAlerts();
  const [alerts, setAlertList] = useState<Alert[]>([]);
  const [q, setQ] = useState("");
  const [runAt, setRunAt] = useState<string>(defaultRunAt);
  const [channel, setChannel] = useState<Channel>("email");
  const [recipient, setRecipient] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setAlertList(await apiGet<Alert[]>("alerts"));
    } catch {
      // listing unavailable; leave empty
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function create() {
    const question = q.trim();
    const rcpt = recipient.trim();
    if (!question || !rcpt || !runAt || busy) return;
    const scheduledIso = new Date(runAt).toISOString();
    setBusy(true);
    try {
      await apiPost<Alert>("alerts", {
        question,
        channel,
        recipient: rcpt,
        scheduled_at: scheduledIso,
      });
      setQ("");
      setRecipient("");
      setRunAt(defaultRunAt());
      notify("success", "Alert scheduled");
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
    <div className={className}>
      <div className="flex items-center gap-1.5 px-1 text-[11px] font-semibold tracking-wide text-[var(--muted)] uppercase">
        <Bell size={12} /> Alerts
      </div>

      <div className="mt-2 space-y-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2">
        <textarea
          rows={2}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Alert me when…"
          className="w-full resize-none rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs outline-none focus:border-[var(--accent)]"
        />
        <div className="px-0.5 text-[10px] leading-snug text-[var(--muted)]">
          e.g.{" "}
          <button
            type="button"
            onClick={() => setQ(EXAMPLES[0])}
            className="italic underline-offset-2 hover:underline"
          >
            “{EXAMPLES[0]}”
          </button>
          <br />
          <button
            type="button"
            onClick={() => setQ(EXAMPLES[1])}
            className="italic underline-offset-2 hover:underline"
          >
            “{EXAMPLES[1]}”
          </button>
        </div>

        <div className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
          <CalendarClock size={12} />
          <span>Run at</span>
          <input
            type="datetime-local"
            value={runAt}
            onChange={(e) => setRunAt(e.target.value)}
            className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--bg)] px-1.5 py-1 text-xs text-[var(--fg)] outline-none focus:border-[var(--accent)]"
          />
        </div>

        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={() => setChannel("email")}
            className={`flex flex-1 items-center justify-center gap-1 rounded-md border px-2 py-1 text-[11px] transition-colors ${
              channel === "email"
                ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                : "border-[var(--border)] bg-[var(--bg)] text-[var(--muted)] hover:text-[var(--fg)]"
            }`}
          >
            <Mail size={11} /> Email
          </button>
          <button
            type="button"
            onClick={() => setChannel("slack")}
            className={`flex flex-1 items-center justify-center gap-1 rounded-md border px-2 py-1 text-[11px] transition-colors ${
              channel === "slack"
                ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                : "border-[var(--border)] bg-[var(--bg)] text-[var(--muted)] hover:text-[var(--fg)]"
            }`}
          >
            <MessageSquare size={11} /> Slack
          </button>
        </div>

        <input
          value={recipient}
          onChange={(e) => setRecipient(e.target.value)}
          placeholder={channel === "email" ? "you@company.com" : "#alerts"}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs outline-none focus:border-[var(--accent)]"
        />

        <button
          type="button"
          onClick={() => void create()}
          disabled={busy || !q.trim() || !recipient.trim() || !runAt}
          className="w-full rounded-md bg-[var(--accent)] px-2 py-1.5 text-xs font-medium text-white disabled:opacity-40"
        >
          Add alert
        </button>
      </div>

      <div className="mt-3 space-y-2">
        {alerts.length === 0 ? (
          <p className="px-1 text-[11px] text-[var(--muted)]">No alerts yet.</p>
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
              <div className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-[var(--muted)]">
                <span>
                  {a.comparator} {a.threshold}
                </span>
                <span>·</span>
                <span className="inline-flex items-center gap-0.5">
                  <CalendarClock size={10} />
                  {a.scheduled_at
                    ? formatScheduled(a.scheduled_at)
                    : `every ${a.cadence_minutes}m`}
                </span>
                <span>·</span>
                <span className="inline-flex items-center gap-0.5">
                  {a.channel === "email" ? (
                    <Mail size={10} />
                  ) : a.channel === "slack" ? (
                    <MessageSquare size={10} />
                  ) : (
                    <Bell size={10} />
                  )}
                  {a.recipient || a.channel}
                </span>
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
                  className="flex items-center gap-1 text-[11px] text-[var(--muted)] hover:text-[var(--danger-fg)]"
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
