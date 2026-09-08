import { RotateCcw, Trash2 } from "lucide-react";
import { OwnerBadge } from "@/components/domain/OwnerBadge";
import { PriorityBadge } from "@/components/domain/PriorityBadge";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api/client";
import { useToast } from "@/lib/toast";
import { useAuth } from "@/features/auth/useAuth";
import { useItem } from "@/features/items/useItem";
import { useDeleteItem, useRestoreItem } from "@/features/items/useItemMutations";
import { DetailsTab } from "./DetailsTab";
import { HistoryTab } from "./HistoryTab";
import { UpdatesTab } from "./UpdatesTab";

export function ItemDetail({ itemId, onClose }: { itemId: number; onClose?: () => void }) {
  const { data: item, isLoading, isError, error } = useItem(itemId);
  const { user } = useAuth();
  const del = useDeleteItem();
  const restore = useRestoreItem();
  const { toast } = useToast();

  if (isLoading) {
    return (
      <div className="space-y-3 p-6">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (isError || !item) {
    const gone = error instanceof ApiError && error.status === 404;
    return (
      <div className="p-6 text-sm text-danger">
        {gone ? "This item no longer exists." : "Could not load this item."}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-6 py-4 pr-10">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs text-fg-muted">#{item.entry_no}</p>
            <h2 className="text-lg font-semibold">{item.title}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={item.status} />
              <PriorityBadge priority={item.priority} />
              <OwnerBadge owner={item.owner_org} />
              {item.deleted_at && <Badge variant="outline">Deleted</Badge>}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {item.deleted_at
              ? user?.role === "admin" && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={async () => {
                      await restore.mutateAsync(item.id);
                      toast({ title: "Item restored", variant: "success" });
                    }}
                  >
                    <RotateCcw className="size-4" /> Restore
                  </Button>
                )
              : !item.deleted_at && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={async () => {
                      await del.mutateAsync(item.id);
                      toast({ title: "Item deleted", variant: "success" });
                      onClose?.();
                    }}
                  >
                    <Trash2 className="size-4" /> Delete
                  </Button>
                )}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        <Tabs defaultValue="details">
          <TabsList className="mb-4">
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="updates">Updates</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
          </TabsList>
          <TabsContent value="details">
            <DetailsTab item={item} />
          </TabsContent>
          <TabsContent value="updates">
            <UpdatesTab itemId={item.id} />
          </TabsContent>
          <TabsContent value="history">
            <HistoryTab itemId={item.id} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
