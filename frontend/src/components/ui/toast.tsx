import * as ToastPrimitive from "@radix-ui/react-toast";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

export const ToastViewport = () => (
  <ToastPrimitive.Viewport className="fixed bottom-0 right-0 z-[100] flex w-96 max-w-[100vw] flex-col gap-2 p-4 outline-none" />
);

export function ToastRoot({
  variant = "default",
  ...props
}: React.ComponentPropsWithoutRef<typeof ToastPrimitive.Root> & {
  variant?: "default" | "success" | "error";
}) {
  return (
    <ToastPrimitive.Root
      className={cn(
        "flex items-start gap-3 rounded-md border bg-surface p-4 shadow-md",
        variant === "error" && "border-danger/40",
        variant === "success" && "border-success/40",
        variant === "default" && "border-border",
      )}
      {...props}
    />
  );
}

export const ToastTitle = ({ className, ...props }: ToastPrimitive.ToastTitleProps) => (
  <ToastPrimitive.Title className={cn("text-sm font-medium text-fg", className)} {...props} />
);
export const ToastDescription = ({ className, ...props }: ToastPrimitive.ToastDescriptionProps) => (
  <ToastPrimitive.Description className={cn("text-sm text-fg-muted", className)} {...props} />
);
export const ToastClose = () => (
  <ToastPrimitive.Close className="ml-auto text-fg-subtle hover:text-fg" aria-label="Dismiss">
    <X className="size-4" />
  </ToastPrimitive.Close>
);
export const ToastProviderPrimitive = ToastPrimitive.Provider;
