"use client";

import {
  createContext,
  type Dispatch,
  type SetStateAction,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

interface CanvasWorkspaceContextValue {
  activeDraftCanvasId: string | null;
  setActiveDraftCanvasId: Dispatch<SetStateAction<string | null>>;
  version: number;
  notifyWorkspaceChanged: () => void;
}

const Ctx = createContext<CanvasWorkspaceContextValue | null>(null);

export function CanvasWorkspaceProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [activeDraftCanvasId, setActiveDraftCanvasId] = useState<string | null>(
    null,
  );
  const [version, setVersion] = useState(0);

  const notifyWorkspaceChanged = useCallback(() => {
    setVersion((v) => v + 1);
  }, []);

  const value = useMemo(
    () => ({
      activeDraftCanvasId,
      setActiveDraftCanvasId,
      version,
      notifyWorkspaceChanged,
    }),
    [activeDraftCanvasId, notifyWorkspaceChanged, version],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCanvasWorkspace(): CanvasWorkspaceContextValue {
  const value = useContext(Ctx);
  if (!value) {
    throw new Error(
      "useCanvasWorkspace must be used inside CanvasWorkspaceProvider",
    );
  }
  return value;
}
