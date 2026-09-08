import { createContext, useCallback, useContext, useMemo, useState } from "react";
import {
  ToastClose,
  ToastDescription,
  ToastProviderPrimitive,
  ToastRoot,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast";

type Variant = "default" | "success" | "error";
interface ToastItem {
  id: number;
  title: string;
  description?: string;
  variant: Variant;
}
interface ToastApi {
  toast: (t: { title: string; description?: string; variant?: Variant }) => void;
}

const ToastContext = createContext<ToastApi | null>(null);
let nextId = 1;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const toast = useCallback<ToastApi["toast"]>(({ title, description, variant = "default" }) => {
    const id = nextId++;
    setItems((prev) => [...prev, { id, title, description, variant }]);
  }, []);

  const remove = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const api = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={api}>
      <ToastProviderPrimitive swipeDirection="right" duration={5000}>
        {children}
        {items.map((t) => (
          <ToastRoot key={t.id} variant={t.variant} onOpenChange={(open) => !open && remove(t.id)}>
            <div className="flex flex-col gap-0.5">
              <ToastTitle>{t.title}</ToastTitle>
              {t.description && <ToastDescription>{t.description}</ToastDescription>}
            </div>
            <ToastClose />
          </ToastRoot>
        ))}
        <ToastViewport />
      </ToastProviderPrimitive>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
