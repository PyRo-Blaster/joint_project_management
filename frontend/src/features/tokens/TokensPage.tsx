import { useState } from "react";
import { KeyRound } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/useAuth";
import type { TokenOut } from "@/lib/api/types";
import { useToast } from "@/lib/toast";
import { NewTokenDialog } from "./NewTokenDialog";
import { TokenRow } from "./TokenRow";
import { useRevokeToken, useTokens } from "./useTokens";

export function TokensPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [showAll, setShowAll] = useState(false);
  const tokens = useTokens(isAdmin && showAll);
  const revoke = useRevokeToken();
  const { toast } = useToast();

  async function onRevoke(token: TokenOut) {
    try {
      await revoke.mutateAsync(token.id);
      toast({
        title: "Token revoked",
        description: `"${token.name}" stops working immediately.`,
      });
    } catch {
      toast({ title: "Could not revoke that token", variant: "error" });
    }
  }

  const rows = tokens.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-base font-semibold">API tokens</h1>
          <p className="max-w-prose text-sm text-fg-muted">
            A token lets an agent read and update the tracker on your behalf, without a browser.
            Every change it makes is recorded against you and marked as coming from an agent.
          </p>
        </div>
        <NewTokenDialog />
      </div>

      {isAdmin && (
        <div className="flex items-center gap-2.5">
          <Checkbox
            id="tokens-all"
            checked={showAll}
            onCheckedChange={(v) => setShowAll(v === true)}
          />
          <Label htmlFor="tokens-all">Show every user&rsquo;s tokens</Label>
        </div>
      )}

      {tokens.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={KeyRound}
          title="No API tokens yet"
          description="Create one to let an agent work on your behalf."
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-fg-muted">
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Prefix</th>
                <th className="px-4 py-2.5 font-medium">Scopes</th>
                <th className="px-4 py-2.5 font-medium">Write mode</th>
                <th className="px-4 py-2.5 font-medium">Last used</th>
                <th className="px-4 py-2.5 font-medium">Expires</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {rows.map((token) => (
                <TokenRow
                  key={token.id}
                  token={token}
                  showOwner={showAll}
                  onRevoke={onRevoke}
                  revoking={revoke.isPending}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
