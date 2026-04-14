/**
 * Pure helpers and constants for interval rendering.
 *
 * Lives in `lib/` (not `components/ui/`) so unit tests and table rows can
 * import without pulling Radix/React. `IntervalSelect` imports the same
 * source of truth from here.
 */

export const INTERVAL_PRESETS = [
  { key: "30s", seconds: 30 },
  { key: "1m", seconds: 60 },
  { key: "5m", seconds: 300 },
  { key: "15m", seconds: 900 },
  { key: "30m", seconds: 1800 },
  { key: "1h", seconds: 3600 },
  { key: "6h", seconds: 21600 },
  { key: "12h", seconds: 43200 },
  { key: "1d", seconds: 86400 },
] as const;

export type IntervalPresetKey = (typeof INTERVAL_PRESETS)[number]["key"];

export const CUSTOM_KEY = "custom" as const;

/** Returns the preset key whose seconds match `value`, or `undefined`. */
export function findPresetKey(value: number): IntervalPresetKey | undefined {
  return INTERVAL_PRESETS.find((p) => p.seconds === value)?.key;
}

/**
 * Given a raw seconds value, return the i18n key to render it.
 *
 * - Matches a preset → returns `"intervals.<preset>"` (e.g. `"intervals.1m"`).
 * - No match → returns `"intervals.custom"`; callers should also render the
 *   seconds count alongside for clarity.
 */
export function intervalLabelKey(
  seconds: number,
): `intervals.${IntervalPresetKey | "custom"}` {
  const preset = INTERVAL_PRESETS.find((p) => p.seconds === seconds);
  return preset ? `intervals.${preset.key}` : "intervals.custom";
}

/**
 * Human-friendly fallback formatter for custom intervals.
 *
 * Used only when a task's `interval_seconds` doesn't match any preset;
 * it's an English-biased debug aid, not a user-facing label.
 */
export function formatCustomSeconds(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}
