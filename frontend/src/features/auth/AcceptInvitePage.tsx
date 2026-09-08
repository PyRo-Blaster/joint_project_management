import { useForm } from "react-hook-form";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { zodResolver } from "@/lib/form";
import { AuthField } from "./AuthField";
import { acceptSchema, type AcceptValues } from "./auth-schema";
import { useAcceptInvite } from "./useAuth";

export function AcceptInvitePage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const accept = useAcceptInvite();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<AcceptValues>({ resolver: zodResolver(acceptSchema) });

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-sm">
          <CardContent className="pt-6 text-sm text-fg-muted">
            This link is missing its token. Ask an administrator for a new invitation link.
          </CardContent>
        </Card>
      </main>
    );
  }

  const onSubmit = handleSubmit(async (values) => {
    try {
      await accept.mutateAsync({ token, name: values.name, password: values.password });
      navigate("/login?accepted=1", { replace: true });
    } catch (error) {
      const message =
        error instanceof ApiError && error.status === 422
          ? "This link is invalid or has expired. Ask for a new one."
          : "Could not complete setup. Try again.";
      setError("root", { message });
    }
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Set up your account</CardTitle>
          <p className="text-sm text-fg-muted">Choose a name and password to finish.</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            <AuthField
              id="name"
              label="Full name"
              autoFocus
              error={errors.name?.message}
              {...register("name")}
            />
            <AuthField
              id="password"
              label="Password"
              type="password"
              autoComplete="new-password"
              error={errors.password?.message}
              {...register("password")}
            />
            <AuthField
              id="confirm"
              label="Confirm password"
              type="password"
              autoComplete="new-password"
              error={errors.confirm?.message}
              {...register("confirm")}
            />
            {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}
            <Button type="submit" disabled={isSubmitting} className="mt-2">
              {isSubmitting ? "Saving…" : "Create account"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
