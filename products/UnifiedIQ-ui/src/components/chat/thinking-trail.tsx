"use client";

import { Brain } from "lucide-react";

import type { ThinkingStep } from "@/lib/types";

export function ThinkingTrail({
  steps,
  live,
}: {
  steps: ThinkingStep[];
  live?: boolean;
}) {
  if (steps.length === 0) return null;
  return (
    <details className="group mb-3 rounded-lg bg-[var(--bg)] px-3 py-2 text-xs text-[var(--muted)]">
      <summary className="flex cursor-pointer items-center gap-1.5 font-medium select-none">
        <Brain size={13} className={live ? "uiq-pulse" : ""} />
        Reasoning
        <span className="text-[var(--muted)]">· {steps.length} steps</span>
      </summary>
      <ol className="mt-2 space-y-1.5 border-l border-[var(--border)] pl-3">
        {steps.map((s, i) => (
          <li key={i}>
            <span className="font-medium text-[var(--fg)]">{s.step}</span>
            {" — "}
            {s.detail}
          </li>
        ))}
      </ol>
    </details>
  );
}
