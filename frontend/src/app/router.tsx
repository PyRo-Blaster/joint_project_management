import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "@/app/layout";
import { RequireAuth } from "@/features/auth/auth-context";
import { LoginPage } from "@/features/auth/login-page";
import { AcceptInvitePage } from "@/features/auth/accept-invite-page";
import { ItemsPage } from "@/features/items/items-page";

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/accept-invite" element={<AcceptInvitePage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/items" replace />} />
        <Route path="/items" element={<ItemsPage />} />
        <Route path="/items/:itemId" element={<ItemsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/items" replace />} />
    </Routes>
  );
}
