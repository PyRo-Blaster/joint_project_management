import { Skeleton } from "@/components/ui/skeleton";
import type { VocabTermOut } from "@/lib/api/types";
import { AddTermRow } from "./AddTermRow";
import { VocabFieldTable } from "./VocabFieldTable";
import { useVocabAdmin } from "./useVocabAdmin";

export function VocabPage() {
  const vocab = useVocabAdmin();

  const rename = (id: number, value: string) => vocab.patch.mutate({ id, value });
  const setActive = (id: number, is_active: boolean) => vocab.patch.mutate({ id, is_active });
  const swap = (a: VocabTermOut, b: VocabTermOut) => {
    vocab.patch.mutate({ id: a.id, sort_order: b.sort_order });
    vocab.patch.mutate({ id: b.id, sort_order: a.sort_order });
  };

  if (vocab.isLoading) return <Skeleton className="h-64 w-full" />;

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
      {(["group", "category"] as const).map((field) => {
        const terms = field === "group" ? vocab.groups : vocab.categories;
        return (
          <section key={field} className="flex flex-col gap-3">
            <h2 className="text-base font-semibold">
              {field === "group" ? "Groups" : "Categories"}
            </h2>
            <VocabFieldTable
              terms={terms}
              onRename={rename}
              onSetActive={setActive}
              onSwap={swap}
            />
            <AddTermRow
              pending={vocab.create.isPending}
              onAdd={(value) =>
                vocab.create.mutate({
                  field,
                  value,
                  sort_order: (terms.at(-1)?.sort_order ?? 0) + 1,
                })
              }
            />
          </section>
        );
      })}
    </div>
  );
}
