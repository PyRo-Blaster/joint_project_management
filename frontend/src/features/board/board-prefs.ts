import { useCallback, useState } from "react";

const KEY = "cmc-board-collapsed";
const DEFAULT = ["completed", "cancelled"];

export function useCollapsedColumns() {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem(KEY);
      return new Set(raw ? (JSON.parse(raw) as string[]) : DEFAULT);
    } catch {
      return new Set(DEFAULT);
    }
  });
  const toggle = useCallback((status: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      try {
        localStorage.setItem(KEY, JSON.stringify([...next]));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);
  return { collapsed, toggle };
}
