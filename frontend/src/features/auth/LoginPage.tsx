import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { zodResolver } from "@/lib/form";
import { AuthField } from "./AuthField";
import { loginSchema, type LoginValues } from "./auth-schema";
import { useLogin } from "./useAuth";

export function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login.mutateAsync(values);
      const params = new URLSearchParams(window.location.search);
      navigate(params.get("returnTo") || "/items", { replace: true });
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        setError("root", { message: "Too many attempts. Wait a minute and try again." });
      } else if (error instanceof ApiError && error.status === 401) {
        setError("root", { message: "Incorrect email or password." });
      } else {
        setError("root", { message: "Sign-in failed. Try again." });
      }
    }
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Joint CMC Tracker</CardTitle>
          <p className="text-sm text-fg-muted">Sign in to continue</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            <AuthField
              id="email"
              label="Email"
              type="email"
              autoComplete="username"
              autoFocus
              error={errors.email?.message}
              {...register("email")}
            />
            <AuthField
              id="password"
              label="Password"
              type="password"
              autoComplete="current-password"
              error={errors.password?.message}
              {...register("password")}
            />
            {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}
            <Button type="submit" disabled={isSubmitting} className="mt-2">
              {isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
