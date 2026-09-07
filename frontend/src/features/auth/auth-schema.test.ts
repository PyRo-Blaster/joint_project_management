import { acceptSchema, loginSchema } from "./auth-schema";

test("loginSchema rejects a bad email and empty password", () => {
  expect(loginSchema.safeParse({ email: "nope", password: "" }).success).toBe(false);
  expect(loginSchema.safeParse({ email: "a@b.co", password: "x" }).success).toBe(true);
});

test("acceptSchema enforces min length and matching confirmation", () => {
  expect(acceptSchema.safeParse({ name: "A", password: "short", confirm: "short" }).success).toBe(
    false,
  );
  expect(
    acceptSchema.safeParse({ name: "A", password: "longenough1", confirm: "different" }).success,
  ).toBe(false);
  expect(
    acceptSchema.safeParse({ name: "A", password: "longenough1", confirm: "longenough1" }).success,
  ).toBe(true);
});
