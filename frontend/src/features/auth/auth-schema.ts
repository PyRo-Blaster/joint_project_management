import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const acceptSchema = z
  .object({
    name: z.string().min(1, "Name is required").max(200),
    password: z.string().min(10, "Use at least 10 characters"),
    confirm: z.string().min(1, "Confirm your password"),
  })
  .refine((v) => v.password === v.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });
export type AcceptValues = z.infer<typeof acceptSchema>;
