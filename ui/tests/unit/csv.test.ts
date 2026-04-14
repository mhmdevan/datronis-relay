import { describe, expect, it } from "vitest";
import { toCsv, type CsvColumn } from "@/lib/csv";

/**
 * Contract tests for the pure CSV serializer.
 *
 * `downloadCsv` is a thin DOM wrapper and is not tested here — the only
 * interesting logic lives in `toCsv` + the internal escape helper, and
 * we exercise both through the public API.
 */
interface Row {
  user_id: string;
  display_name: string | null;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
}

const COLUMNS: CsvColumn<Row>[] = [
  { key: "user_id", label: "User ID" },
  { key: "display_name", label: "Display name" },
  { key: "tokens_in", label: "Tokens In" },
  { key: "tokens_out", label: "Tokens Out" },
  {
    key: "cost_usd",
    label: "Cost (USD)",
    format: (v) => (typeof v === "number" ? v.toFixed(4) : String(v)),
  },
];

describe("toCsv", () => {
  it("emits the header line when rows are empty", () => {
    expect(toCsv([] as Row[], COLUMNS)).toBe(
      "User ID,Display name,Tokens In,Tokens Out,Cost (USD)",
    );
  });

  it("serializes simple rows", () => {
    const rows: Row[] = [
      {
        user_id: "telegram:1",
        display_name: "Alice",
        tokens_in: 100,
        tokens_out: 200,
        cost_usd: 1.234567,
      },
    ];
    const out = toCsv(rows, COLUMNS);
    expect(out.split("\n")).toEqual([
      "User ID,Display name,Tokens In,Tokens Out,Cost (USD)",
      "telegram:1,Alice,100,200,1.2346",
    ]);
  });

  it("renders null/undefined as empty fields", () => {
    const rows: Row[] = [
      {
        user_id: "slack:U1",
        display_name: null,
        tokens_in: 0,
        tokens_out: 0,
        cost_usd: 0,
      },
    ];
    const out = toCsv(rows, COLUMNS);
    expect(out).toContain("slack:U1,,0,0,0.0000");
  });

  it("escapes commas inside a field by wrapping in quotes", () => {
    const rows: Row[] = [
      {
        user_id: "telegram:1",
        display_name: "Doe, Jane",
        tokens_in: 1,
        tokens_out: 1,
        cost_usd: 0,
      },
    ];
    const out = toCsv(rows, COLUMNS);
    expect(out).toContain('"Doe, Jane"');
  });

  it("escapes embedded double quotes by doubling them", () => {
    const rows: Row[] = [
      {
        user_id: "telegram:1",
        display_name: 'Alice "Ace"',
        tokens_in: 1,
        tokens_out: 1,
        cost_usd: 0,
      },
    ];
    const out = toCsv(rows, COLUMNS);
    expect(out).toContain('"Alice ""Ace"""');
  });

  it("escapes newlines inside a field", () => {
    const rows: Row[] = [
      {
        user_id: "telegram:1",
        display_name: "Line1\nLine2",
        tokens_in: 1,
        tokens_out: 1,
        cost_usd: 0,
      },
    ];
    const out = toCsv(rows, COLUMNS);
    expect(out).toContain('"Line1\nLine2"');
  });

  it("uses the column `format` override when provided", () => {
    const rows: Row[] = [
      {
        user_id: "telegram:1",
        display_name: "Alice",
        tokens_in: 1,
        tokens_out: 1,
        cost_usd: 99.999999,
      },
    ];
    const out = toCsv(rows, COLUMNS);
    expect(out.split("\n")[1]).toContain("100.0000");
  });
});
