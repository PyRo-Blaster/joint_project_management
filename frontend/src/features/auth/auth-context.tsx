import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { useMeQuery, useLogoutMutation } from "@/lib/api/hooks";
import type { UserOut } from "@/lib/api/types";
import { SESSION_EXPIRED_EVENT } from "@/lib/constants";
import { queryKeys } from "@/lib/query-keys";
import { useQueryClient } from "@tanstack/react-query";

type AuthContextValue = {
  user: UserOut | null | undefined;
  isLoading: boolean;
  isAuthenticated: boolean;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const me = useMeQuery();
  const logoutMutation = useLogoutMutation();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();

  const onSessionExpired = useCallback(() => {
    qc.setQueryData(queryKeys.me, null);
    if (!location.pathname.startsWith("/login") && !location.pathname.startsWith("/accept-invite")) {
      toast.message("Session expired — please sign in again");
      const next = encodeURIComponent(location.pathname + location.search);
      navigate(`/login?next=${next}`, { replace: true });
    }
  }, [qc, location.pathname, location.search, navigate]);

  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED_EVENT, onSessionExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onSessionExpired);
  }, [onSessionExpired]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: me.data,
      isLoading: me.isLoading,
      isAuthenticated: Boolean(me.data),
      logout: () => {
        logoutMutation.mutate(undefined, {
          onSettled: () => navigate("/login", { replace: true }),
        });
      },
    }),
    [me.data, me.isLoading, logoutMutation, navigate],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      const next = encodeURIComponent(location.pathname + location.search);
      navigate(`/login?next=${next}`, { replace: true });
    }
  }, [isAuthenticated, isLoading, location.pathname, location.search, navigate]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-ink-muted">
        Checking session…
      </div>
    );
  }
  if (!isAuthenticated) return null;
  return children;
}
