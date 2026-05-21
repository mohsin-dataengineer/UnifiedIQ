"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Code2,
  HelpCircle,
  Loader2,
  RefreshCcw,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";

import { ApiError, apiPost } from "@/lib/api-client";
import type { VerificationResult } from "@/lib/types";

const VERDICT_STYLE: Record<
  VerificationResult["verdict"],
  { cls: string; icon: React.ReactNode; label: string }
> = {
  agree: {
    cls: "bg-[var(--success-bg)] text-[var(--success-fg)] ring-[var(--success-border)]",
    icon: <CheckCircle2 size={14} />,
    label: "Verified",
  },
  disagree: {
    cls: "bg-[var(--danger-bg)] text-[var(--danger-fg)] ring-[var(--danger-border)]",
    icon: <AlertTriangle size={14} />,
    label: "Disagreement",
  },
  inconclusive: {
    cls: "bg-[var(--warning-bg)] text-[var(--warning-fg)] ring-[var(--warning-border)]",
    icon: <HelpCircle size={14} />,
    label: "Inconclusive",
  },
};

function fmtPct(p: number | null | undefined): string | null {
  if (p === null || p === undefined) return null;
  return `${(p * 100).toFixed(2)}%`;
}

function fmtNum(n: number | null | undefined): string | null {
  if (n === null || n === undefined) return null;
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(
    n,
  );
}

export function VerifyPanel({
  question,
  sql,
}: {
  question: string;
  sql: string;
}) {
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const r = await apiPost<VerificationResult>("chat/verify", {
        question,
        original_sql: sql,
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  }

  if (!result && !loading && !error) {
    return (
      <button
        type="button"
        onClick={() => void run()}
        className="flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
        title="Cross-check this answer by re-deriving the metric a different way"
      >
        <ShieldCheck size={13} /> Verify
      </button>
    );
  }

  if (loading) {
    return (
      <span className="flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)]">
        <Loader2 size={13} className="animate-spin" /> Verifying…
      </span>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2">
        <span className="rounded-md bg-[var(--danger-bg)] px-2 py-1 text-xs text-[var(--danger-fg)]">
          {error}
        </span>
        <button
          type="button"
          onClick={() => void run()}
          className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)] hover:text-[var(--fg)]"
        >
          <RefreshCcw size={12} className="inline" /> Retry
        </button>
      </div>
    );
  }

  // result is non-null below
  const r = result!;
  const style = VERDICT_STYLE[r.verdict];

  return (
    <div className="mt-3 w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${style.cls}`}
        >
          {style.icon} {style.label}
        </span>
        <span className="text-[11px] text-[var(--muted)]">
          confidence{" "}
          <span className="font-semibold text-[var(--fg)]">
            {(r.confidence * 100).toFixed(0)}%
          </span>
        </span>
        {r.diff_pct !== undefined && r.diff_pct !== null && (
          <span className="text-[11px] text-[var(--muted)]">
            · relative diff{" "}
            <span className="font-semibold text-[var(--fg)]">
              {fmtPct(r.diff_pct)}
            </span>
          </span>
        )}
        <button
          type="button"
          onClick={() => void run()}
          className="ml-auto rounded-md border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--muted)] hover:text-[var(--fg)]"
          title="Re-verify"
        >
          <RefreshCcw size={11} className="inline" /> Re-verify
        </button>
      </div>

      {r.original_value !== null &&
        r.original_value !== undefined &&
        r.alternative_value !== null &&
        r.alternative_value !== undefined && (
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-md bg-[var(--surface)] p-2">
              <div className="text-[10px] font-medium text-[var(--muted)] uppercase">
                Original
              </div>
              <div className="text-base font-semibold text-[var(--fg)]">
                {fmtNum(r.original_value)}
              </div>
            </div>
            <div className="rounded-md bg-[var(--surface)] p-2">
              <div className="text-[10px] font-medium text-[var(--muted)] uppercase">
                Independent recompute
              </div>
              <div className="text-base font-semibold text-[var(--fg)]">
                {fmtNum(r.alternative_value)}
              </div>
            </div>
          </div>
        )}

      <p className="mt-2 text-xs text-[var(--fg)]">{r.rationale}</p>

      {r.alternative_sql && (
        <details className="mt-2 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs">
          <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-[var(--muted)] select-none">
            <Code2 size={13} /> Alternative SQL
            {r.alternative_approach && (
              <span className="ml-1 text-[10px] font-normal text-[var(--muted)]">
                — {r.alternative_approach}
              </span>
            )}
          </summary>
          <pre className="mt-2 overflow-x-auto font-mono text-[11px] leading-relaxed text-[var(--fg)]">
            {r.alternative_sql}
          </pre>
        </details>
      )}
    </div>
  );
}
