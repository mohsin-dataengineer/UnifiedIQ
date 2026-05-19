"use client";

import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

import { useAlerts } from "@/contexts/alert-context";

const STYLE: Record<string, { cls: string; icon: React.ReactNode }> = {
  info: {
    cls: "bg-[var(--fg)] text-white",
    icon: <Info size={15} />,
  },
  error: {
    cls: "bg-red-600 text-white",
    icon: <AlertTriangle size={15} />,
  },
  success: {
    cls: "bg-green-600 text-white",
    icon: <CheckCircle2 size={15} />,
  },
};

export function AlertHost() {
  const { alerts, dismiss } = useAlerts();
  if (alerts.length === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 flex-col gap-2">
      {alerts.map((a) => {
        const s = STYLE[a.level];
        return (
          <div
            key={a.id}
            className={`uiq-animate-in flex items-center gap-2.5 rounded-xl px-4 py-2.5 text-sm shadow-lg ${s.cls}`}
          >
            {s.icon}
            <span>{a.message}</span>
            <button
              type="button"
              onClick={() => dismiss(a.id)}
              className="ml-1 opacity-70 transition-opacity hover:opacity-100"
              aria-label="Dismiss"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
