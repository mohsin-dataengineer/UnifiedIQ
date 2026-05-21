"use client";

import { Code2, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ResultView } from "@/components/chat/result-view";
import { ThinkingTrail } from "@/components/chat/thinking-trail";
import type { ChatTurn } from "@/contexts/conversation-context";

export function Message({
  turn,
  streaming,
}: {
  turn: ChatTurn;
  streaming?: boolean;
}) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end uiq-animate-in">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-[var(--accent)] px-4 py-2.5 text-sm text-white shadow-sm">
          {turn.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 uiq-animate-in">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[var(--accent)]">
        <Sparkles size={16} />
      </div>
      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-md border border-[var(--border)] bg-[var(--surface)] px-4 py-3 shadow-sm">
        {turn.thinking && (
          <ThinkingTrail steps={turn.thinking} live={streaming} />
        )}

        {turn.sql && (
          <details className="mb-3 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-xs">
            <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-[var(--muted)] select-none">
              <Code2 size={13} /> Generated SQL
            </summary>
            <pre className="mt-2 overflow-x-auto font-mono text-[11px] leading-relaxed text-[var(--fg)]">
              {turn.sql}
            </pre>
            {turn.assumptions && turn.assumptions.length > 0 && (
              <ul className="mt-2 list-disc pl-4 text-[var(--muted)]">
                {turn.assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            )}
          </details>
        )}

        {turn.chart && turn.chartData && turn.chartData.length > 0 && (
          <ResultView
            spec={turn.chart}
            data={turn.chartData}
            question={turn.question}
            sql={turn.sql}
          />
        )}

        {turn.content && (
          <div className="prose prose-sm mt-3 max-w-none text-[var(--fg)]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {turn.content}
            </ReactMarkdown>
          </div>
        )}

        {streaming && !turn.content && !turn.error && (
          <div className="flex gap-1 py-1">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--muted)] uiq-pulse" />
            <span
              className="h-1.5 w-1.5 rounded-full bg-[var(--muted)] uiq-pulse"
              style={{ animationDelay: "0.2s" }}
            />
            <span
              className="h-1.5 w-1.5 rounded-full bg-[var(--muted)] uiq-pulse"
              style={{ animationDelay: "0.4s" }}
            />
          </div>
        )}

        {turn.error && (
          <p className="mt-2 rounded-lg bg-[var(--danger-bg)] px-3 py-2 text-xs text-[var(--danger-fg)]">
            {turn.error}
          </p>
        )}

        {turn.citations && turn.citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2 border-t border-[var(--border)] pt-2">
            {turn.citations.map((c) =>
              c.url ? (
                <a
                  key={c.id}
                  href={c.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-full bg-[var(--bg)] px-2.5 py-0.5 text-xs text-[var(--muted)] hover:text-[var(--fg)]"
                >
                  {c.title}
                </a>
              ) : (
                <span
                  key={c.id}
                  className="rounded-full bg-[var(--bg)] px-2.5 py-0.5 text-xs text-[var(--muted)]"
                >
                  {c.title}
                </span>
              ),
            )}
          </div>
        )}
      </div>
    </div>
  );
}
