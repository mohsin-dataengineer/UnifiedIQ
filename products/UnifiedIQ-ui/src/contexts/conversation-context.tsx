"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type {
  ChartSpec,
  Citation,
  Row,
  ThinkingStep,
} from "@/lib/types";

export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  sql?: string;
  assumptions?: string[];
  chart?: ChartSpec;
  chartData?: Row[];
  citations?: Citation[];
  thinking?: ThinkingStep[];
  error?: string;
}

interface ConversationContextValue {
  turns: ChatTurn[];
  addTurn: (turn: ChatTurn) => void;
  patchLast: (patch: Partial<ChatTurn>) => void;
  appendToLast: (text: string) => void;
  reset: () => void;
}

const ConversationContext = createContext<ConversationContextValue | null>(
  null,
);

// Conversation history is persisted in localStorage keyed by user_email
// (Part 3.6), so it never leaks across identities on a shared machine.
function storageKey(userEmail: string): string {
  return `unifiediq:conversation:${userEmail}`;
}

export function ConversationProvider({
  userEmail,
  children,
}: {
  userEmail: string;
  children: React.ReactNode;
}) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey(userEmail));
      setTurns(raw ? (JSON.parse(raw) as ChatTurn[]) : []);
    } catch {
      setTurns([]);
    }
  }, [userEmail]);

  useEffect(() => {
    localStorage.setItem(storageKey(userEmail), JSON.stringify(turns));
  }, [userEmail, turns]);

  const addTurn = useCallback((turn: ChatTurn) => {
    setTurns((prev) => [...prev, turn]);
  }, []);

  const patchLast = useCallback((patch: Partial<ChatTurn>) => {
    setTurns((prev) => {
      if (prev.length === 0) return prev;
      const next = prev.slice();
      next[next.length - 1] = { ...next[next.length - 1], ...patch };
      return next;
    });
  }, []);

  const appendToLast = useCallback((text: string) => {
    setTurns((prev) => {
      if (prev.length === 0) return prev;
      const next = prev.slice();
      const last = next[next.length - 1];
      next[next.length - 1] = { ...last, content: last.content + text };
      return next;
    });
  }, []);

  const reset = useCallback(() => setTurns([]), []);

  const value = useMemo(
    () => ({ turns, addTurn, patchLast, appendToLast, reset }),
    [turns, addTurn, patchLast, appendToLast, reset],
  );

  return (
    <ConversationContext.Provider value={value}>
      {children}
    </ConversationContext.Provider>
  );
}

export function useConversation(): ConversationContextValue {
  const ctx = useContext(ConversationContext);
  if (!ctx) {
    throw new Error(
      "useConversation must be used within ConversationProvider",
    );
  }
  return ctx;
}
