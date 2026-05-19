"use client";

import { AlertHost } from "@/components/ui/alert-host";
import { AlertProvider } from "@/contexts/alert-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AlertProvider>
      {children}
      <AlertHost />
    </AlertProvider>
  );
}
