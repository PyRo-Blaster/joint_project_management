import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";

export function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <p className="text-5xl font-semibold text-fg-subtle">404</p>
      <p className="text-fg-muted">That page does not exist.</p>
      <Link to="/items" className={buttonVariants()}>
        Back to items
      </Link>
    </div>
  );
}
