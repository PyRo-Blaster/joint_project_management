import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";
import { NotFound } from "@/app/NotFound";
import { ItemDetail } from "./ItemDetail";

/** Full-page detail for deep links (e.g. shared URLs, refresh on /items/42). */
export function ItemDetailPage() {
  const { id } = useParams();
  const itemId = id ? Number(id) : NaN;
  if (Number.isNaN(itemId)) return <NotFound />;
  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/items" className={`${buttonVariants({ variant: "ghost", size: "sm" })} mb-3`}>
        <ArrowLeft className="size-4" /> Back to items
      </Link>
      <div className="rounded-lg border border-border bg-surface">
        <ItemDetail itemId={itemId} />
      </div>
    </div>
  );
}
