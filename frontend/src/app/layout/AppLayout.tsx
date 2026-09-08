import { Outlet } from "react-router-dom";
import { useAuthExpiredRedirect } from "@/app/useAuthExpiredRedirect";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppLayout() {
  useAuthExpiredRedirect();
  return (
    <div className="flex min-h-screen flex-col">
      <Topbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 overflow-x-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
