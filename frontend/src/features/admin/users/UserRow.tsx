import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { UserOut } from "@/lib/api/types";
import { ORGS, ROLES } from "@/lib/constants";
import { ORG_LABELS } from "@/lib/labels";
import { RelativeTime } from "@/components/domain/RelativeTime";
import { usePatchUser } from "./useUsersAdmin";

export function UserRow({
  user,
  onResetLink,
}: {
  user: UserOut;
  onResetLink: (u: UserOut) => void;
}) {
  const patch = usePatchUser();
  return (
    <tr className="border-b border-border/60 last:border-0">
      <td className="px-4 py-3">
        <div className="font-medium">{user.name}</div>
        <div className="text-xs text-fg-muted">{user.email}</div>
      </td>
      <td className="px-4 py-3">
        <Select
          value={user.org}
          onValueChange={(org) => patch.mutate({ id: user.id, patch: { org: org as never } })}
        >
          <SelectTrigger className="h-8 w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ORGS.map((o) => (
              <SelectItem key={o} value={o}>
                {ORG_LABELS[o]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </td>
      <td className="px-4 py-3">
        <Select
          value={user.role}
          onValueChange={(role) => patch.mutate({ id: user.id, patch: { role: role as never } })}
        >
          <SelectTrigger className="h-8 w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLES.map((r) => (
              <SelectItem key={r} value={r}>
                {r === "admin" ? "Admin" : "Member"}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </td>
      <td className="px-4 py-3">
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={user.is_active}
            onCheckedChange={(v) => patch.mutate({ id: user.id, patch: { is_active: !!v } })}
          />
          {user.is_active ? "Active" : "Inactive"}
        </label>
      </td>
      <td className="px-4 py-3 text-sm text-fg-muted">
        <RelativeTime iso={user.last_login_at} />
      </td>
      <td className="px-4 py-3 text-right">
        <Button variant="outline" size="sm" onClick={() => onResetLink(user)}>
          <KeyRound className="size-4" /> Reset link
        </Button>
      </td>
    </tr>
  );
}
