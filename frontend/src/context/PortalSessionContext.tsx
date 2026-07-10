/* eslint-disable react-refresh/only-export-components -- provider + hook in one module */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  clearChatConversation,
  getPortalSessionFromStorage,
  setAuthToken,
  type PortalSession,
} from "../api/client";

type PortalSessionContextValue = {
  session: PortalSession | null;
  setSession: (s: PortalSession | null) => void;
  logout: () => void;
};

const PortalSessionContext = createContext<PortalSessionContextValue | null>(null);

export function PortalSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<PortalSession | null>(() =>
    getPortalSessionFromStorage()
  );

  const logout = useCallback(() => {
    setAuthToken(null);
    clearChatConversation();
    setSession(null);
  }, []);

  const value = useMemo(
    () => ({ session, setSession, logout }),
    [session, logout]
  );

  return (
    <PortalSessionContext.Provider value={value}>{children}</PortalSessionContext.Provider>
  );
}

export function usePortalSession(): PortalSessionContextValue {
  const ctx = useContext(PortalSessionContext);
  if (!ctx) {
    throw new Error("usePortalSession must be used within PortalSessionProvider");
  }
  return ctx;
}
