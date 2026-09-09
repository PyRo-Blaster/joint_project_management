import type { ItemOut } from "@/lib/api/types";
import { useToast } from "@/lib/toast";
import { ItemForm } from "@/features/items/ItemForm";
import { itemToFormValues } from "@/features/items/item-schema";
import { usePatchItem } from "@/features/items/useItemMutations";

export function DetailsTab({ item }: { item: ItemOut }) {
  const patch = usePatchItem(item.id);
  const { toast } = useToast();
  return (
    <ItemForm
      // Switching kind here toggles the item between action and note; the PATCH
      // endpoint coerces the status to match (cleared for a note, defaulted for
      // an action).
      defaultValues={itemToFormValues(item)}
      submitLabel="Save changes"
      onSubmit={async (payload) => {
        await patch.mutateAsync(payload);
        toast({ title: "Changes saved", variant: "success" });
      }}
    />
  );
}
