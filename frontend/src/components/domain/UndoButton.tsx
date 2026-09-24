import { Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { useToast } from "@/lib/toast";
import { useRevertChange } from "@/features/items/useItemMutations";

/** Undo one recorded change. The server explains any refusal, e.g. a field changed since. */
export function UndoButton({ itemId, eventId }: { itemId: number; eventId: number }) {
  const revert = useRevertChange(itemId);
  const { toast } = useToast();
  return (
    <Button
      variant="ghost"
      size="sm"
      disabled={revert.isPending}
      onClick={async () => {
        try {
          await revert.mutateAsync(eventId);
          toast({ title: "Change undone", variant: "success" });
        } catch (error) {
          toast({
            title: "Could not undo that change",
            description: error instanceof ApiError ? error.message : undefined,
            variant: "error",
          });
        }
      }}
    >
      <Undo2 className="size-4" /> Undo
    </Button>
  );
}
