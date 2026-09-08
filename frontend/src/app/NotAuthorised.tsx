import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";

export function NotAuthorised() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <p className="text-lg font-semibold">Admins only</p>
      <p className="text-fg-muted">You do not have permission to view this page.</p>
      <Link to="/dashboard" className={buttonVariants({ variant: "outline" })}>
        Back to dashboard
      </Link>
    </div>
  );
}
