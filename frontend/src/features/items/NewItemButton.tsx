import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useToast } from "@/lib/toast";
import { ItemForm } from "./ItemForm";
import { NEW_ITEM_DEFAULTS } from "./item-schema";
import { useCreateItem } from "./useItemMutations";
import { useVocab } from "./useVocab";

export function NewItemButton() {
  const [open, setOpen] = useState(false);
  const create = useCreateItem();
  const { toast } = useToast();
  const { groups } = useVocab();

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="size-4" /> New item
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New item</DialogTitle>
        </DialogHeader>
        <div className="overflow-y-auto px-6 py-4">
          <ItemForm
            defaultValues={{ ...NEW_ITEM_DEFAULTS, group: groups[0]?.value ?? "" }}
            submitLabel="Create item"
            onCancel={() => setOpen(false)}
            onSubmit={async (payload) => {
              const item = await create.mutateAsync(payload);
              toast({ title: `Created #${item.entry_no}`, variant: "success" });
              setOpen(false);
            }}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
