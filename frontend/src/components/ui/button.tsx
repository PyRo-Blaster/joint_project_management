import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const variants = {
  primary:
    "bg-accent text-accent-fg hover:opacity-90 focus-visible:ring-accent shadow-sm",
  secondary:
    "bg-surface-raised text-ink border border-line hover:bg-surface-muted focus-visible:ring-accent",
  ghost: "text-ink-muted hover:bg-surface-muted hover:text-ink focus-visible:ring-accent",
  danger: "bg-rose-600 text-white hover:bg-rose-700 focus-visible:ring-rose-500",
} as const;

const sizes = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-base",
} as const;

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
