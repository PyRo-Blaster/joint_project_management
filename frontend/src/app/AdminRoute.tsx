import { Outlet } from "react-router-dom";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/features/auth/useAuth";
import { NotAuthorised } from "./NotAuthorised";

/** Nested inside ProtectedRoute; the user is authenticated, so this only checks the role. */
export function AdminRoute() {
  const { user, isFetched } = useAuth();
  if (!isFetched) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner className="size-6" />
      </div>
    );
  }
  return user?.role === "admin" ? <Outlet /> : <NotAuthorised />;
}
