/** Locale-aware formatting of the few quantities the UI shows. */

export interface DurationParts {
  hours: number;
  minutes: number;
  /** True when less than a minute is left. */
  imminent: boolean;
}

/** Split a duration for display, rounded to the minute. */
export function durationParts(seconds: number): DurationParts {
  const totalMinutes = Math.max(0, Math.round(seconds / 60));
  return {
    hours: Math.floor(totalMinutes / 60),
    minutes: totalMinutes % 60,
    imminent: seconds < 45,
  };
}

/** "10:45" in the user's locale conventions. */
export function formatClock(epochMs: number, locale: string): string {
  return new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" }).format(epochMs);
}

/** "850 m" below 1 km, "3,4 km" above (one decimal below 20 km). */
export function formatDistance(meters: number, locale: string): string {
  if (meters < 1000) {
    return `${new Intl.NumberFormat(locale).format(Math.round(meters / 10) * 10)} m`;
  }
  const km = meters / 1000;
  const digits = km < 20 ? 1 : 0;
  return `${new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(km)} km`;
}

/** Elevation gain / loss, rounded to 10 m (finer would be false precision). */
export function formatClimb(meters: number, locale: string): string {
  return `${new Intl.NumberFormat(locale).format(Math.round(meters / 10) * 10)} m`;
}

/** "5 s ago" / "hace 3 min" — short relative time for "last update". */
export function formatAgo(seconds: number, locale: string): string {
  const relative = new Intl.RelativeTimeFormat(locale, { numeric: "always", style: "short" });
  if (seconds < 60) return relative.format(-Math.round(seconds), "second");
  if (seconds < 3600) return relative.format(-Math.round(seconds / 60), "minute");
  return relative.format(-Math.round(seconds / 3600), "hour");
}

/** Whole minutes in a span of seconds (for "stopped for 12 min"). */
export function wholeMinutes(seconds: number): number {
  return Math.max(1, Math.round(seconds / 60));
}
