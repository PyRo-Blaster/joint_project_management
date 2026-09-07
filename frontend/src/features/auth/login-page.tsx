import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { FieldError } from "@/components/ui/field-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { applyApiFieldErrors, toastApiError, useLoginMutation } from "@/lib/api/hooks";
import { useAuth } from "@/features/auth/auth-context";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const login = useLoginMutation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next") || "/items";

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  if (!isLoading && isAuthenticated) {
    return <Navigate to={next} replace />;
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <div className="mb-8">
        <p className="text-sm font-medium uppercase tracking-[0.18em] text-accent">GS098</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Joint CMC Tracker</h1>
        <p className="mt-2 text-ink-muted">Sign in with your invite-provisioned account.</p>
      </div>
      <form
        className="space-y-4 rounded-xl border border-line bg-surface-raised p-6 shadow-sm"
        onSubmit={handleSubmit(async (values) => {
          try {
            await login.mutateAsync(values);
            navigate(next, { replace: true });
          } catch (error) {
            if (!applyApiFieldErrors(error, setError)) toastApiError(error, "Sign-in failed");
          }
        })}
      >
        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="username" {...register("email")} />
          <FieldError message={errors.email?.message} />
        </div>
        <div>
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            {...register("password")}
          />
          <FieldError message={errors.password?.message} />
        </div>
        <Button className="w-full" type="submit" disabled={isSubmitting || login.isPending}>
          {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-ink-muted">
        Have an invite or reset link?{" "}
        <Link className="font-medium text-accent hover:underline" to="/accept-invite">
          Accept invite
        </Link>
      </p>
    </div>
  );
}
