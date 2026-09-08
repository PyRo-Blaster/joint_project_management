import type { FieldError, FieldValues, Resolver } from "react-hook-form";
import type { ZodType } from "zod";

/** Adapt a zod schema to react-hook-form without pulling in @hookform/resolvers. */
export function zodResolver<T extends FieldValues>(schema: ZodType<T>): Resolver<T> {
  return async (values) => {
    const result = schema.safeParse(values);
    if (result.success) return { values: result.data, errors: {} };
    const errors: Record<string, FieldError> = {};
    for (const issue of result.error.issues) {
      const path = issue.path.join(".");
      if (path && !errors[path]) errors[path] = { type: issue.code, message: issue.message };
    }
    return { values: {} as T, errors: errors as never };
  };
}
