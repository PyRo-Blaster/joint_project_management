import type { ItemListParams } from "@/lib/api/types";

export const queryKeys = {
  me: ["auth", "me"] as const,
  items: (params: ItemListParams) => ["items", params] as const,
  item: (id: number) => ["item", id] as const,
  itemUpdates: (id: number) => ["item", id, "updates"] as const,
  itemHistory: (id: number) => ["item", id, "history"] as const,
  vocab: (field?: string) => ["vocab", field ?? "all"] as const,
  users: ["users"] as const,
};
