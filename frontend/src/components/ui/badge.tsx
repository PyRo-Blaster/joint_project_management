import { cn } from "@/lib/utils";

const tones: Record<string, string> = {
  default: "bg-slate-100 text-slate-700 ring-slate-200",
  open: "bg-sky-50 text-sky-800 ring-sky-200",
  in_progress: "bg-amber-50 text-amber-900 ring-amber-200",
  blocked: "bg-rose-50 text-rose-800 ring-rose-200",
  on_hold: "bg-violet-50 text-violet-800 ring-violet-200",
  completed: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  cancelled: "bg-slate-100 text-slate-500 ring-slate-200",
  p1: "bg-rose-100 text-rose-800 ring-rose-200",
  p2: "bg-orange-50 text-orange-800 ring-orange-200",
  p3: "bg-slate-100 text-slate-600 ring-slate-200",
  gensci: "bg-cyan-50 text-cyan-900 ring-cyan-200",
  yarrow: "bg-indigo-50 text-indigo-900 ring-indigo-200",
  joint: "bg-teal-50 text-teal-900 ring-teal-200",
  note: "bg-fuchsia-50 text-fuchsia-900 ring-fuchsia-200",
};

export function Badge({
  children,
  tone = "default",
  className,
}: {
  children: React.ReactNode;
  tone?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        tones[tone] ?? tones.default,
        className,
      )}
    >
      {children}
    </span>
  );
}
