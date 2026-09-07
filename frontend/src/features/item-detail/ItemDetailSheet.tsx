import { useSearchParams } from "react-router-dom";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { ItemDetail } from "./ItemDetail";

/** Reads `?selected=<id>` and shows the item in a right-side sheet over the list. */
export function ItemDetailSheet() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selected = searchParams.get("selected");
  const id = selected ? Number(selected) : null;

  function close() {
    const params = new URLSearchParams(searchParams);
    params.delete("selected");
    setSearchParams(params);
  }

  return (
    <Sheet open={id != null} onOpenChange={(open) => !open && close()}>
      <SheetContent className="p-0" aria-describedby={undefined}>
        {id != null && <ItemDetail itemId={id} onClose={close} />}
      </SheetContent>
    </Sheet>
  );
}
