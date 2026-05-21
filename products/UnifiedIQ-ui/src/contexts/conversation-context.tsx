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
  question?: string;
  sql?: string;
  assumptions?: string[];
  chart?: ChartSpec;
  chartData?: Row[];
  citations?: Citation[];
  thinking?: ThinkingStep[];
  error?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  turns: ChatTurn[];
  created_at: string;
  updated_at: string;
}

interface ConversationContextValue {
  sessions: ChatSession[];
  activeSessionId: string;
  turns: ChatTurn[];
  newChat: () => void;
  switchTo: (id: string) => void;
  deleteChat: (id: string) => void;
  renameChat: (id: string, title: string) => void;
  addTurn: (turn: ChatTurn) => void;
  patchLast: (patch: Partial<ChatTurn>) => void;
  appendToLast: (text: string) => void;
}

const ConversationContext = createContext<ConversationContextValue | null>(
  null,
);

const DEFAULT_TITLE = "New chat";
const TITLE_LIMIT = 60;

// Multi-session history is persisted in localStorage keyed by user_email,
// so it never leaks across identities on a shared machine.
function storageKey(userEmail: string): string {
  return `unifiediq:sessions:${userEmail}`;
}
function legacyKey(userEmail: string): string {
  return `unifiediq:conversation:${userEmail}`;
}

interface PersistedState {
  sessions: ChatSession[];
  activeSessionId: string;
}

function newSession(): ChatSession {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: DEFAULT_TITLE,
    turns: [],
    created_at: now,
    updated_at: now,
  };
}

function deriveTitle(turns: ChatTurn[]): string {
  const firstUser = turns.find((t) => t.role === "user" && t.content.trim());
  if (!firstUser) return DEFAULT_TITLE;
  const trimmed = firstUser.content.trim().replace(/\s+/g, " ");
  return trimmed.length > TITLE_LIMIT
    ? trimmed.slice(0, TITLE_LIMIT - 1) + "…"
    : trimmed;
}

function loadState(userEmail: string): PersistedState {
  try {
    const raw = localStorage.getItem(storageKey(userEmail));
    if (raw) {
      const parsed = JSON.parse(raw) as PersistedState;
      if (parsed.sessions && parsed.sessions.length > 0) return parsed;
    }
    // One-time migration of the older single-thread layout, so existing
    // users don't lose their last conversation.
    const legacyRaw = localStorage.getItem(legacyKey(userEmail));
    if (legacyRaw) {
      const legacyTurns = JSON.parse(legacyRaw) as ChatTurn[];
      if (Array.isArray(legacyTurns) && legacyTurns.length > 0) {
        const s = newSession();
        s.turns = legacyTurns;
        s.title = deriveTitle(legacyTurns);
        localStorage.removeItem(legacyKey(userEmail));
        return { sessions: [s], activeSessionId: s.id };
      }
    }
  } catch {
    // fall through to fresh state
  }
  const fresh = newSession();
  return { sessions: [fresh], activeSessionId: fresh.id };
}

export function ConversationProvider({
  userEmail,
  children,
}: {
  userEmail: string;
  children: React.ReactNode;
}) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>("");

  useEffect(() => {
    const s = loadState(userEmail);
    setSessions(s.sessions);
    setActiveSessionId(s.activeSessionId);
  }, [userEmail]);

  useEffect(() => {
    if (!activeSessionId) return;
    localStorage.setItem(
      storageKey(userEmail),
      JSON.stringify({ sessions, activeSessionId } satisfies PersistedState),
    );
  }, [userEmail, sessions, activeSessionId]);

  const turns = useMemo(
    () => sessions.find((s) => s.id === activeSessionId)?.turns ?? [],
    [sessions, activeSessionId],
  );

  const newChat = useCallback(() => {
    setSessions((prev) => {
      // Don't create endless empty drafts: if the active session is empty,
      // just reuse it.
      const active = prev.find((s) => s.id === activeSessionId);
      if (active && active.turns.length === 0) return prev;
      const s = newSession();
      setActiveSessionId(s.id);
      return [s, ...prev];
    });
  }, [activeSessionId]);

  const switchTo = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const deleteChat = useCallback(
    (id: string) => {
      setSessions((prev) => {
        const next = prev.filter((s) => s.id !== id);
        if (next.length === 0) {
          const s = newSession();
          setActiveSessionId(s.id);
          return [s];
        }
        if (id === activeSessionId) setActiveSessionId(next[0].id);
        return next;
      });
    },
    [activeSessionId],
  );

  const renameChat = useCallback((id: string, title: string) => {
    const clean = title.trim();
    if (!clean) return;
    setSessions((prev) =>
      prev.map((s) =>
        s.id === id
          ? { ...s, title: clean, updated_at: new Date().toISOString() }
          : s,
      ),
    );
  }, []);

  function mutateActive(transform: (turns: ChatTurn[]) => ChatTurn[]) {
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== activeSessionId) return s;
        const nextTurns = transform(s.turns);
        const nextTitle =
          s.title === DEFAULT_TITLE ? deriveTitle(nextTurns) : s.title;
        return {
          ...s,
          turns: nextTurns,
          title: nextTitle,
          updated_at: new Date().toISOString(),
        };
      }),
    );
  }

  const addTurn = useCallback(
    (turn: ChatTurn) => mutateActive((t) => [...t, turn]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeSessionId],
  );

  const patchLast = useCallback(
    (patch: Partial<ChatTurn>) =>
      mutateActive((t) => {
        if (t.length === 0) return t;
        const next = t.slice();
        next[next.length - 1] = { ...next[next.length - 1], ...patch };
        return next;
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeSessionId],
  );

  const appendToLast = useCallback(
    (text: string) =>
      mutateActive((t) => {
        if (t.length === 0) return t;
        const next = t.slice();
        const last = next[next.length - 1];
        next[next.length - 1] = { ...last, content: last.content + text };
        return next;
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeSessionId],
  );

  const value = useMemo(
    () => ({
      sessions,
      activeSessionId,
      turns,
      newChat,
      switchTo,
      deleteChat,
      renameChat,
      addTurn,
      patchLast,
      appendToLast,
    }),
    [
      sessions,
      activeSessionId,
      turns,
      newChat,
      switchTo,
      deleteChat,
      renameChat,
      addTurn,
      patchLast,
      appendToLast,
    ],
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
