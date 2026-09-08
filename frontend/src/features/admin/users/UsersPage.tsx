import { useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { RelativeTime } from "@/components/domain/RelativeTime";
import type { UserOut } from "@/lib/api/types";
import { ORG_LABELS } from "@/lib/labels";
import { InviteDialog } from "./InviteDialog";
import { ResetLinkDialog } from "./ResetLinkDialog";
import { UserRow } from "./UserRow";
import { useInvitations, useRevokeInvitation, useUsersList } from "./useUsersAdmin";

export function UsersPage() {
  const users = useUsersList();
  const invitations = useInvitations();
  const revoke = useRevokeInvitation();
  const [resetUser, setResetUser] = useState<UserOut | null>(null);
  const pending = (invitations.data ?? []).filter((i) => !i.accepted_at);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Users</h2>
        <InviteDialog />
      </div>

      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        {users.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-fg-muted">
                <th className="px-4 py-2.5 font-medium">User</th>
                <th className="px-4 py-2.5 font-medium">Org</th>
                <th className="px-4 py-2.5 font-medium">Role</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Last login</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {(users.data ?? []).map((u) => (
                <UserRow key={u.id} user={u} onResetLink={setResetUser} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Pending invitations</CardTitle>
        </CardHeader>
        <CardContent>
          {pending.length === 0 ? (
            <p className="text-sm text-fg-subtle">No pending invitations.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {pending.map((inv) => (
                <li key={inv.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <span>
                    <span className="font-medium">{inv.email}</span>{" "}
                    <span className="text-fg-muted">
                      · {ORG_LABELS[inv.org ?? ""] ?? inv.org} · expires{" "}
                      <RelativeTime iso={inv.expires_at} />
                    </span>
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => revoke.mutate(inv.id)}
                    aria-label={`Revoke invitation for ${inv.email}`}
                  >
                    <Trash2 className="size-4" /> Revoke
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-fg-subtle">
            The one-time invitation link is shown once, when you create it. Revoke and re-invite if
            it was lost.
          </p>
        </CardContent>
      </Card>

      <ResetLinkDialog user={resetUser} onClose={() => setResetUser(null)} />
    </div>
  );
}
