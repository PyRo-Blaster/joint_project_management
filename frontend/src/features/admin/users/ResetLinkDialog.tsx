import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { CopyButton } from "@/components/ui/copy-button";
import { Spinner } from "@/components/ui/spinner";
import type { UserOut } from "@/lib/api/types";
import { useResetLink } from "./useUsersAdmin";

/** Opens when `user` is set; requests a one-time reset link and shows it to copy. */
export function ResetLinkDialog({ user, onClose }: { user: UserOut | null; onClose: () => void }) {
  const reset = useResetLink();
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      setUrl(null);
      return;
    }
    reset.mutate(user.id, { onSuccess: (data) => setUrl(data.url) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  return (
    <Dialog open={!!user} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Password reset link</DialogTitle>
          <DialogDescription>
            Send this one-time link to {user?.name}. It expires and can be used once.
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-2 px-6 py-4">
          {url ? (
            <>
              <Input readOnly value={url} className="font-mono text-xs" />
              <CopyButton value={url} />
            </>
          ) : reset.isError ? (
            <p className="text-sm text-danger">Could not create a reset link.</p>
          ) : (
            <Spinner />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
