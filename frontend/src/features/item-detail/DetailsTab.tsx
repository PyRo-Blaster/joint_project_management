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
      // `kind` is included in the payload but ignored by the PATCH endpoint (kind is immutable).
      defaultValues={itemToFormValues(item)}
      submitLabel="Save changes"
      onSubmit={async (payload) => {
        await patch.mutateAsync(payload);
        toast({ title: "Changes saved", variant: "success" });
      }}
    />
  );
}
