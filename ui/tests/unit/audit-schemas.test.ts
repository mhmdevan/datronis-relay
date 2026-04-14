import { describe, expect, it } from "vitest";
import {
  auditEntrySchema,
  auditEventTypeSchema,
  auditResponseSchema,
} from "@/lib/schemas";
import { buildQuery } from "@/lib/api";

describe("auditEventTypeSchema", () => {
  const types = [
    "msg_in",
    "msg_out",
    "auth_fail",
    "rate_limit",
    "claude_ok",
    "claude_error",
  ];

  it("accepts every event type from the Python backend", () => {
    for (const type of types) {
      expect(auditEventTypeSchema.safeParse(type).success).toBe(true);
    }
  });

  it("rejects unknown event types", () => {
    expect(auditEventTypeSchema.safeParse("banana").success).toBe(false);
  });
});

describe("auditEntrySchema", () => {
  const base = {
    ts: "2026-04-15T10:00:00Z",
    correlation_id: "abc-123",
    user_id: "telegram:1",
    event_type: "claude_ok",
  };

  it("accepts a minimal entry with only required fields", () => {
    expect(auditEntrySchema.safeParse(base).success).toBe(true);
  });

  it("accepts every optional field populated", () => {
    const full = {
      ...base,
      tool: "Read",
      command: "cat file.txt",
      exit_code: 0,
      duration_ms: 1234,
      tokens_in: 100,
      tokens_out: 200,
      cost_usd: 0.05,
      error_category: null,
    };
    expect(auditEntrySchema.safeParse(full).success).toBe(true);
  });

  it("accepts null cost_usd (no pricing data recorded)", () => {
    expect(
      auditEntrySchema.safeParse({ ...base, cost_usd: null }).success,
    ).toBe(true);
  });

  it("rejects an entry missing correlation_id", () => {
    const { correlation_id: _drop, ...rest } = base;
    void _drop;
    expect(auditEntrySchema.safeParse(rest).success).toBe(false);
  });
});

describe("auditResponseSchema", () => {
  it("accepts a response with a next_cursor", () => {
    expect(
      auditResponseSchema.safeParse({
        entries: [],
        next_cursor: "opaque-cursor",
      }).success,
    ).toBe(true);
  });

  it("accepts a response with a null next_cursor", () => {
    expect(
      auditResponseSchema.safeParse({ entries: [], next_cursor: null })
        .success,
    ).toBe(true);
  });

  it("accepts a response without next_cursor at all", () => {
    expect(auditResponseSchema.safeParse({ entries: [] }).success).toBe(true);
  });
});

describe("buildQuery", () => {
  it("returns an empty string for an empty object", () => {
    expect(buildQuery({})).toBe("");
  });

  it("returns an empty string when every value is undefined", () => {
    expect(buildQuery({ a: undefined, b: null })).toBe("");
  });

  it("skips empty-string values", () => {
    expect(buildQuery({ a: "", b: "v" })).toBe("?b=v");
  });

  it("serializes present values with `?` prefix", () => {
    const out = buildQuery({ days: 30, user_id: "telegram:1" });
    expect(out).toBe("?days=30&user_id=telegram%3A1");
  });

  it("coerces numbers to strings", () => {
    expect(buildQuery({ limit: 50 })).toBe("?limit=50");
  });

  it("treats `null` as absence, not as the literal 'null'", () => {
    expect(buildQuery({ cursor: null })).toBe("");
  });
});
