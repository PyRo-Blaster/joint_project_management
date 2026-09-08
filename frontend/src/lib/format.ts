/** All dates from the API are ISO `YYYY-MM-DD` (date) or ISO datetime strings (UTC, naive). */

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

const RELATIVE_STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31536000],
  ["month", 2592000],
  ["week", 604800],
  ["day", 86400],
  ["hour", 3600],
  ["minute", 60],
];

/** "3 days ago", "in 2 hours", "just now". `now` is injectable for tests. */
export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "—";
  const then = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : `${iso}Z`);
  if (Number.isNaN(then.getTime())) return "—";
  const diffSeconds = Math.round((then.getTime() - now.getTime()) / 1000);
  const abs = Math.abs(diffSeconds);
  if (abs < 45) return "just now";
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, secs] of RELATIVE_STEPS) {
    if (abs >= secs) return rtf.format(Math.round(diffSeconds / secs), unit);
  }
  return "just now";
}

/** A due date is overdue when it is strictly before today (date-only comparison). */
export function isOverdue(dueOn: string | null | undefined, today: Date = new Date()): boolean {
  if (!dueOn) return false;
  const due = new Date(`${dueOn}T00:00:00`);
  const midnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return due.getTime() < midnight.getTime();
}

/** Days until due (negative if past). null when there is no due date. */
export function daysUntil(
  dueOn: string | null | undefined,
  today: Date = new Date(),
): number | null {
  if (!dueOn) return null;
  const due = new Date(`${dueOn}T00:00:00`);
  const midnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((due.getTime() - midnight.getTime()) / 86400000);
}
