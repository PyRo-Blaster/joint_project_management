import { OWNER_LABELS } from "@/lib/labels";
import type { OwnerOrg } from "@/lib/constants";

export function OwnerBadge({ owner }: { owner: string }) {
  const label = OWNER_LABELS[owner as OwnerOrg] ?? owner;
  const dot = (org: "gensci" | "yarrow") => (
    <span className="size-2 rounded-full" style={{ backgroundColor: `var(--org-${org})` }} />
  );
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      {owner === "joint" ? (
        <span className="flex items-center -space-x-0.5">
          {dot("gensci")}
          {dot("yarrow")}
        </span>
      ) : (
        dot(owner as "gensci" | "yarrow")
      )}
      {label}
    </span>
  );
}
