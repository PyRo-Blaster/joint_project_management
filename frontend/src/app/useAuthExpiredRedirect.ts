import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { AUTH_EXPIRED_EVENT } from "@/lib/api/client";
import { qk, queryClient } from "@/lib/query";

/** When any request 401s, drop the cached user and bounce to /login with a returnTo. */
export function useAuthExpiredRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    const onExpired = () => {
      queryClient.setQueryData(qk.auth.me(), null);
      const path = window.location.pathname + window.location.search;
      if (window.location.pathname.startsWith("/login")) return;
      navigate(`/login?returnTo=${encodeURIComponent(path)}`, { replace: true });
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [navigate]);
}
