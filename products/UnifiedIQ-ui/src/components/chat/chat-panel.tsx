"use client";

import { ArrowUp, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Message } from "@/components/chat/message";
import { NotificationsBell } from "@/components/chat/notifications-bell";
import { Sidebar, SUGGESTIONS } from "@/components/chat/sidebar";
import { useAlerts } from "@/contexts/alert-context";
import { useConversation } from "@/contexts/conversation-context";
import { streamChat } from "@/lib/api-client";
import { readSSE } from "@/lib/sse";
import type { ChartSpec, Citation, Row, ThinkingStep } from "@/lib/types";

export function ChatPanel({ email }: { email: string }) {
  const { turns, addTurn, patchLast, appendToLast, reset } = useConversation();
  const { notify } = useAlerts();
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const sessionRef = useRef<string | undefined>(undefined);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  function stop() {
    abortRef.current?.abort();
  }

  async function send(question: string) {
    const q = question.trim();
    if (!q || streaming) return;
    setInput("");

    const history = turns.map((t) => ({ role: t.role, content: t.content }));
    addTurn({ id: crypto.randomUUID(), role: "user", content: q });
    addTurn({
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      thinking: [],
    });

    setStreaming(true);
    const controller = new AbortController();
    abortRef.current = controller;
    const thinking: ThinkingStep[] = [];
    const citations: Citation[] = [];

    try {
      const res = await streamChat(
        { question: q, session_id: sessionRef.current, history },
        controller.signal,
      );
      if (!res.ok) {
        patchLast({ error: `Request failed (${res.status})` });
        notify("error", "Chat request failed");
        return;
      }
      for await (const msg of readSSE(res)) {
        const d = msg.data as Record<string, unknown>;
        switch (msg.event) {
          case "thinking":
            thinking.push(d as unknown as ThinkingStep);
            patchLast({ thinking: [...thinking] });
            break;
          case "sql":
            patchLast({
              sql: d.sql as string,
              assumptions: (d.assumptions as string[]) ?? [],
            });
            break;
          case "chart":
            patchLast({
              chart: d.chart_config as ChartSpec,
              chartData: (d.data_snapshot as Row[]) ?? [],
            });
            break;
          case "data":
            appendToLast(String(d.text ?? ""));
            break;
          case "citation":
            citations.push(d as unknown as Citation);
            patchLast({ citations: [...citations] });
            break;
          case "done":
            sessionRef.current = (
              d.metadata as { session_id?: string }
            )?.session_id;
            break;
          case "error":
            patchLast({ error: String(d.message ?? "Stream error") });
            notify("error", String(d.message ?? "Stream error"));
            break;
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        patchLast({ error: "Stopped." });
      } else {
        patchLast({ error: "Unexpected error." });
        notify("error", "Unexpected error while streaming");
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  return (
    <div className="flex h-screen">
      <Sidebar email={email} onNewChat={reset} onPick={(q) => void send(q)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-6 py-4">
          <div>
            <h1 className="text-base font-semibold text-[var(--fg)]">
              Ask your data
            </h1>
            <p className="text-xs text-[var(--muted)]">
              Natural-language KPIs, visualizations, and always-on alerts
            </p>
          </div>
          <NotificationsBell />
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto max-w-3xl space-y-5">
            {turns.length === 0 ? (
              <div className="mt-16 text-center">
                <h2 className="text-2xl font-semibold text-[var(--fg)]">
                  What do you want to know?
                </h2>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Ask a question in plain English — get KPIs, tables, and
                  charts.
                </p>
                <div className="mx-auto mt-6 flex max-w-xl flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => void send(s)}
                      className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3.5 py-1.5 text-xs text-[var(--fg)] shadow-sm transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              turns.map((t, i) => (
                <Message
                  key={t.id}
                  turn={t}
                  streaming={
                    streaming &&
                    i === turns.length - 1 &&
                    t.role === "assistant"
                  }
                />
              ))
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="border-t border-[var(--border)] bg-[var(--surface)] px-6 py-4">
          <form
            className="mx-auto flex max-w-3xl items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void send(input);
            }}
          >
            <textarea
              rows={1}
              className="max-h-32 flex-1 resize-none rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-3 text-sm text-[var(--fg)] outline-none focus:border-[var(--accent)]"
              placeholder="Ask about your data…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send(input);
                }
              }}
              disabled={streaming}
            />
            {streaming ? (
              <button
                type="button"
                onClick={stop}
                className="flex h-11 w-11 items-center justify-center rounded-xl border border-[var(--border)] text-[var(--muted)] transition-colors hover:text-[var(--fg)]"
                aria-label="Stop"
              >
                <Square size={16} />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--accent)] text-white transition-opacity hover:opacity-90 disabled:opacity-40"
                aria-label="Send"
              >
                <ArrowUp size={18} />
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
