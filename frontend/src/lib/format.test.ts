import { daysUntil, isOverdue, relativeTime } from "./format";

const NOW = new Date("2026-09-06T12:00:00Z");

test("relativeTime renders past and present", () => {
  expect(relativeTime("2026-09-06T12:00:00", NOW)).toBe("just now");
  expect(relativeTime("2026-09-03T12:00:00", NOW)).toMatch(/3 days ago/);
});

test("isOverdue and daysUntil compare by calendar day", () => {
  const today = new Date("2026-09-06T09:00:00");
  expect(isOverdue("2026-09-05", today)).toBe(true);
  expect(isOverdue("2026-09-06", today)).toBe(false);
  expect(daysUntil("2026-09-09", today)).toBe(3);
  expect(daysUntil(null, today)).toBeNull();
});
