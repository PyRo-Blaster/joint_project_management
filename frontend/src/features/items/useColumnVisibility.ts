import { useCallback, useState } from "react";
import { COLUMNS, DEFAULT_VISIBLE } from "./columns";

const KEY = "cmc-item-columns";

export function useColumnVisibility() {
  const [visible, setVisible] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) return new Set(JSON.parse(raw) as string[]);
    } catch {
      /* storage may be unavailable */
    }
    return new Set(DEFAULT_VISIBLE);
  });

  const toggle = useCallback((id: string) => {
    setVisible((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        localStorage.setItem(KEY, JSON.stringify([...next]));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  // Title anchors the row and cannot be hidden.
  const columns = COLUMNS.map((c) => ({ id: c.id, header: c.header, locked: c.id === "title" }));
  return { visible, toggle, columns };
}
