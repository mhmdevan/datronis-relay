/**
 * Tiny client-side CSV helpers.
 *
 * Kept library-free and pure so they can be unit-tested in a node
 * environment — `downloadCsv` is the only function that touches the DOM
 * and is only called from browser event handlers.
 *
 * RFC 4180-ish escaping:
 *   - Wrap a field in double quotes if it contains `,`, `"` or newlines.
 *   - Double up any embedded double quotes.
 *   - Serialize `null` / `undefined` as empty strings.
 */

export interface CsvColumn<T> {
  /** Key on the row whose value to read. */
  key: keyof T;
  /** Column header as rendered in the output. */
  label: string;
  /**
   * Optional value transform (e.g. format a number). Receives the raw
   * cell value and returns the string the CSV should emit.
   */
  format?: (value: T[keyof T], row: T) => string;
}

/**
 * Serialize a list of rows to a CSV string.
 *
 * @throws never — empty input yields just the header line.
 */
export function toCsv<T extends object>(
  rows: readonly T[],
  columns: readonly CsvColumn<T>[],
): string {
  const header = columns.map((c) => escapeField(c.label)).join(",");
  const body = rows.map((row) =>
    columns
      .map((c) => {
        const raw = row[c.key];
        const str = c.format ? c.format(raw as T[keyof T], row) : stringify(raw);
        return escapeField(str);
      })
      .join(","),
  );
  return [header, ...body].join("\n");
}

/**
 * Trigger a browser download of `csv` as `filename`.
 *
 * Must be called from a user-initiated event (otherwise Safari blocks the
 * programmatic click). No-op on the server.
 */
export function downloadCsv(filename: string, csv: string): void {
  if (typeof window === "undefined") return;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

function stringify(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function escapeField(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}
