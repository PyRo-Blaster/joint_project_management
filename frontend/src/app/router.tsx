import { Navigate, Route, Routes } from "react-router-dom";
import { AcceptInvitePage } from "@/features/auth/AcceptInvitePage";
import { LoginPage } from "@/features/auth/LoginPage";
import { ItemsPage } from "@/features/items/ItemsPage";
import { ItemDetailPage } from "@/features/item-detail/ItemDetailPage";
import { AppLayout } from "./layout/AppLayout";
import { NotFound } from "./NotFound";
import { ProtectedRoute } from "./ProtectedRoute";

// Phase 3 screens (dashboard, board, admin) land later.
function ComingSoon({ title }: { title: string }) {
  return <p className="text-fg-muted">{title} arrives in Phase 3.</p>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/accept-invite" element={<AcceptInvitePage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/items" replace />} />
          <Route path="/items" element={<ItemsPage />} />
          <Route path="/items/:id" element={<ItemDetailPage />} />
          <Route path="/dashboard" element={<ComingSoon title="Dashboard" />} />
          <Route path="/board" element={<ComingSoon title="Board" />} />
          <Route path="/admin" element={<ComingSoon title="Admin" />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
