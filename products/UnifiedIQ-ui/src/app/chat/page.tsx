"use client";

import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { ConversationProvider } from "@/contexts/conversation-context";

interface Me {
  email: string;
  name?: string | null;
}

export default function ChatPage() {
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    fetch("/api/me")
      .then((r) => (r.ok ? r.json() : null))
      .then((d: Me | null) => setMe(d ?? { email: "anonymous" }))
      .catch(() => setMe({ email: "anonymous" }));
  }, []);

  if (!me) {
    return (
      <main className="flex h-screen items-center justify-center text-sm text-[var(--muted)]">
        Loading…
      </main>
    );
  }

  return (
    <ConversationProvider userEmail={me.email}>
      <ChatPanel email={me.email} />
    </ConversationProvider>
  );
}
