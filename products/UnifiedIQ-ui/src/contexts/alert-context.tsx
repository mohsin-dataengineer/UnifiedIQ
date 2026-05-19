"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

type Level = "info" | "error" | "success";

interface Alert {
  id: string;
  level: Level;
  message: string;
}

interface AlertContextValue {
  alerts: Alert[];
  notify: (level: Level, message: string) => void;
  dismiss: (id: string) => void;
}

const AlertContext = createContext<AlertContextValue | null>(null);

export function AlertProvider({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  const dismiss = useCallback((id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const notify = useCallback((level: Level, message: string) => {
    const id = crypto.randomUUID();
    setAlerts((prev) => [...prev, { id, level, message }]);
    // Auto-dismiss so stale toasts don't linger across later questions.
    setTimeout(() => {
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    }, 5000);
  }, []);

  const value = useMemo(
    () => ({ alerts, notify, dismiss }),
    [alerts, notify, dismiss],
  );

  return (
    <AlertContext.Provider value={value}>{children}</AlertContext.Provider>
  );
}

export function useAlerts(): AlertContextValue {
  const ctx = useContext(AlertContext);
  if (!ctx) throw new Error("useAlerts must be used within AlertProvider");
  return ctx;
}
