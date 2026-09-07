import { ITEM_COLUMNS, type ItemColumnId } from "@/lib/constants";

const STORAGE_KEY = "cmc.items.columns";

export function defaultVisibleColumns(): ItemColumnId[] {
  return ITEM_COLUMNS.filter((c) => c.defaultVisible).map((c) => c.id);
}

export function loadVisibleColumns(): ItemColumnId[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultVisibleColumns();
    const parsed = JSON.parse(raw) as string[];
    const allowed = new Set(ITEM_COLUMNS.map((c) => c.id));
    const filtered = parsed.filter((id): id is ItemColumnId => allowed.has(id as ItemColumnId));
    return filtered.length ? filtered : defaultVisibleColumns();
  } catch {
    return defaultVisibleColumns();
  }
}

export function saveVisibleColumns(ids: ItemColumnId[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}
