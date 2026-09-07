import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { FieldError } from "@/components/ui/field-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  applyApiFieldErrors,
  toastApiError,
  useAcceptInviteMutation,
} from "@/lib/api/hooks";
import { MIN_PASSWORD_LENGTH } from "@/lib/constants";

const schema = z
  .object({
    token: z.string().min(1, "Token is required"),
    name: z.string().min(1, "Name is required").max(200),
    password: z.string().min(MIN_PASSWORD_LENGTH, `Password must be at least ${MIN_PASSWORD_LENGTH} characters`),
    confirm: z.string().min(1, "Confirm your password"),
  })
  .refine((v) => v.password === v.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

type FormValues = z.infer<typeof schema>;

export function AcceptInvitePage() {
  const [params] = useSearchParams();
  const accept = useAcceptInviteMutation();
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { token: params.get("token") ?? "" },
  });

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <div className="mb-8">
        <p className="text-sm font-medium uppercase tracking-[0.18em] text-accent">Account</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Accept invite / reset</h1>
        <p className="mt-2 text-ink-muted">
          Set your display name and a password of at least {MIN_PASSWORD_LENGTH} characters.
        </p>
      </div>
      <form
        className="space-y-4 rounded-xl border border-line bg-surface-raised p-6 shadow-sm"
        onSubmit={handleSubmit(async (values) => {
          try {
            await accept.mutateAsync({
              token: values.token,
              name: values.name,
              password: values.password,
            });
            navigate("/login", { replace: true });
          } catch (error) {
            if (!applyApiFieldErrors(error, setError)) toastApiError(error, "Could not accept invite");
          }
        })}
      >
        <div>
          <Label htmlFor="token">Invite / reset token</Label>
          <Input id="token" {...register("token")} />
          <FieldError message={errors.token?.message} />
        </div>
        <div>
          <Label htmlFor="name">Display name</Label>
          <Input id="name" autoComplete="name" {...register("name")} />
          <FieldError message={errors.name?.message} />
        </div>
        <div>
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
          <FieldError message={errors.password?.message} />
        </div>
        <div>
          <Label htmlFor="confirm">Confirm password</Label>
          <Input id="confirm" type="password" autoComplete="new-password" {...register("confirm")} />
          <FieldError message={errors.confirm?.message} />
        </div>
        <Button className="w-full" type="submit" disabled={isSubmitting || accept.isPending}>
          {accept.isPending ? "Saving…" : "Create account"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-ink-muted">
        Already set up?{" "}
        <Link className="font-medium text-accent hover:underline" to="/login">
          Sign in
        </Link>
      </p>
    </div>
  );
}
