import { Navigate, Route, Routes } from "react-router-dom";
import { AcceptInvitePage } from "@/features/auth/AcceptInvitePage";
import { LoginPage } from "@/features/auth/LoginPage";
import { ItemsPage } from "@/features/items/ItemsPage";
import { ItemDetailPage } from "@/features/item-detail/ItemDetailPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { BoardPage } from "@/features/board/BoardPage";
import { AdminLayout } from "@/features/admin/AdminLayout";
import { UsersPage } from "@/features/admin/users/UsersPage";
import { VocabPage } from "@/features/admin/vocab/VocabPage";
import { ImportPage } from "@/features/admin/import/ImportPage";
import { ExportPage } from "@/features/admin/export/ExportPage";
import { AdminRoute } from "./AdminRoute";
import { AppLayout } from "./layout/AppLayout";
import { NotFound } from "./NotFound";
import { ProtectedRoute } from "./ProtectedRoute";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/accept-invite" element={<AcceptInvitePage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/items" element={<ItemsPage />} />
          <Route path="/items/:id" element={<ItemDetailPage />} />
          <Route path="/board" element={<BoardPage />} />
          <Route path="/admin" element={<AdminRoute />}>
            <Route element={<AdminLayout />}>
              <Route index element={<Navigate to="/admin/users" replace />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="vocab" element={<VocabPage />} />
              <Route path="import" element={<ImportPage />} />
              <Route path="export" element={<ExportPage />} />
            </Route>
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
