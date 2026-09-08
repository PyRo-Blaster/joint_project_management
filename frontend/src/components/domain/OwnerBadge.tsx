import { OWNER_LABELS } from "@/lib/labels";
import type { OwnerOrg } from "@/lib/constants";

export function OwnerBadge({ owner }: { owner: string }) {
  const label = OWNER_LABELS[owner as OwnerOrg] ?? owner;
  const dot = (org: "org_a" | "org_b") => (
    <span className="size-2 rounded-full" style={{ backgroundColor: `var(--org-${org})` }} />
  );
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      {owner === "joint" ? (
        <span className="flex items-center -space-x-0.5">
          {dot("org_a")}
          {dot("org_b")}
        </span>
      ) : (
        dot(owner as "org_a" | "org_b")
      )}
      {label}
    </span>
  );
}
