import { useState } from "react";
import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { CopyButton } from "@/components/ui/copy-button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError } from "@/lib/api/client";
import { useCreateToken } from "./useTokens";

type WriteMode = "append" | "interactive";

export function NewTokenDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [canWrite, setCanWrite] = useState(false);
  const [writeMode, setWriteMode] = useState<WriteMode>("interactive");
  const [issued, setIssued] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const create = useCreateToken();

  function reset() {
    setName("");
    setCanWrite(false);
    setWriteMode("interactive");
    setIssued(null);
    setError(null);
  }

  async function submit() {
    setError(null);
    try {
      const result = await create.mutateAsync({
        name,
        scopes: canWrite ? ["read", "write"] : ["read"],
        write_mode: writeMode,
      });
      setIssued(result.token);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the token.");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <KeyRound className="size-4" /> New token
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{issued ? "Token created" : "New API token"}</DialogTitle>
        </DialogHeader>

        {issued ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-fg-muted">
              Copy it now. It is not stored and cannot be shown again.
            </p>
            <div className="flex items-center gap-2 rounded-md border border-border bg-surface-2 p-3">
              <code className="min-w-0 flex-1 break-all font-mono text-xs">{issued}</code>
              <CopyButton value={issued} />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="token-name">Name</Label>
              <Input
                id="token-name"
                value={name}
                placeholder="Claude Code on my laptop"
                onChange={(e) => setName(e.target.value)}
              />
              <p className="text-xs text-fg-subtle">
                So you can tell your tokens apart in the audit trail.
              </p>
            </div>

            <div className="flex items-start gap-2.5">
              <Checkbox
                id="token-write"
                checked={canWrite}
                onCheckedChange={(v) => setCanWrite(v === true)}
              />
              <div className="flex flex-col gap-0.5">
                <Label htmlFor="token-write">Allow writing</Label>
                <p className="text-xs text-fg-subtle">
                  Without this the token can only read. It can never delete anything.
                </p>
              </div>
            </div>

            {canWrite && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="token-mode">Write mode</Label>
                <Select value={writeMode} onValueChange={(v) => setWriteMode(v as WriteMode)}>
                  <SelectTrigger id="token-mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="append">Append only: post updates and add items</SelectItem>
                    <SelectItem value="interactive">Interactive: edits need confirming</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            {error && <p className="text-sm text-danger">{error}</p>}
          </div>
        )}

        <DialogFooter>
          {issued ? (
            <Button onClick={() => setOpen(false)}>Done</Button>
          ) : (
            <Button onClick={submit} disabled={!name.trim() || create.isPending}>
              Create token
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
