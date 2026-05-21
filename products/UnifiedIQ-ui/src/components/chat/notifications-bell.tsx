"use client";

import { Bell } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { apiGet } from "@/lib/api-client";
import type { NotificationItem } from "@/lib/types";

export function NotificationsBell() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [open, setOpen] = useState(false);
  const seenRef = useRef(0);
  const [unread, setUnread] = useState(0);

  const poll = useCallback(async () => {
    try {
      const n = await apiGet<NotificationItem[]>("notifications");
      setItems(n);
      setUnread(Math.max(0, n.length - seenRef.current));
    } catch {
      // notifications unavailable; ignore
    }
  }, []);

  useEffect(() => {
    void poll();
    const t = setInterval(() => void poll(), 20000);
    return () => clearInterval(t);
  }, [poll]);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) {
      seenRef.current = items.length;
      setUnread(0);
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={toggle}
        className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--muted)] transition-colors hover:text-[var(--fg)]"
        aria-label="Notifications"
      >
        <Bell size={16} />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--danger-fg)] px-1 text-[10px] font-semibold text-white">
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-2 shadow-lg">
          <div className="px-2 py-1 text-xs font-semibold text-[var(--fg)]">
            Alert notifications
          </div>
          {items.length === 0 ? (
            <p className="px-2 py-3 text-xs text-[var(--muted)]">
              Nothing yet. Alerts fire here when a threshold is breached.
            </p>
          ) : (
            <div className="max-h-80 space-y-1 overflow-y-auto">
              {items.map((n) => (
                <div key={n.id} className="rounded-lg bg-[var(--bg)] px-3 py-2">
                  <div className="text-xs font-medium text-[var(--fg)]">
                    {n.title}
                  </div>
                  <div className="text-[11px] text-[var(--muted)]">
                    {n.message}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
