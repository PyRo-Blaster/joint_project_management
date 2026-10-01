import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RelativeTime } from "@/components/domain/RelativeTime";
import type { TokenOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

const MODE_LABELS: Record<string, string> = {
  append: "Append only",
  interactive: "Interactive",
};

export function TokenRow({
  token,
  showOwner,
  onRevoke,
  revoking,
}: {
  token: TokenOut;
  showOwner: boolean;
  onRevoke: (token: TokenOut) => void;
  revoking: boolean;
}) {
  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-4 py-3">
        <div className="font-medium">{token.name}</div>
        {showOwner && <div className="text-xs text-fg-subtle">{token.user_name}</div>}
      </td>
      <td className="px-4 py-3">
        <code className="font-mono text-xs text-fg-muted">{token.prefix}</code>
      </td>
      <td className="px-4 py-3 text-fg-muted">{token.scopes.join(", ")}</td>
      <td className="px-4 py-3 text-fg-muted">
        {MODE_LABELS[token.write_mode] ?? token.write_mode}
      </td>
      <td className="px-4 py-3 text-fg-muted">
        {token.last_used_at ? <RelativeTime iso={token.last_used_at} /> : "Never used"}
      </td>
      <td className="px-4 py-3">
        {token.is_active ? (
          <span className="text-fg-muted">
            {token.expires_at ? formatDate(token.expires_at) : "Never expires"}
          </span>
        ) : (
          <Badge variant="neutral">{token.revoked_at ? "Revoked" : "Expired"}</Badge>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        {token.is_active && (
          <Button variant="ghost" size="sm" disabled={revoking} onClick={() => onRevoke(token)}>
            Revoke
          </Button>
        )}
      </td>
    </tr>
  );
}
