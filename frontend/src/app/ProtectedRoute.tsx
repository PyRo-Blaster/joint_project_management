import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/features/auth/useAuth";

/** Gate for authenticated routes. While `/auth/me` resolves, show a spinner. */
export function ProtectedRoute() {
  const { isAuthenticated, isFetched } = useAuth();
  const location = useLocation();

  if (!isFetched) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="size-6" />
      </div>
    );
  }
  if (!isAuthenticated) {
    const returnTo = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?returnTo=${returnTo}`} replace />;
  }
  return <Outlet />;
}
