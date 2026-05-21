"use client";

import { AlertHost } from "@/components/ui/alert-host";
import { AlertProvider } from "@/contexts/alert-context";
import { CanvasWorkspaceProvider } from "@/contexts/canvas-workspace-context";
import { ThemeProvider } from "@/contexts/theme-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <CanvasWorkspaceProvider>
        <AlertProvider>
          {children}
          <AlertHost />
        </AlertProvider>
      </CanvasWorkspaceProvider>
    </ThemeProvider>
  );
}
