import { describe, expect, it } from "vitest";
import {
  dailyCostPointSchema,
  dailyCostResponseSchema,
  perUserCostResponseSchema,
  userCostRowSchema,
} from "@/lib/schemas";
import {
  sortCostRows,
  type PerUserSortKey,
} from "@/components/cost/cost-per-user-table";

describe("userCostRowSchema", () => {
  const valid = {
    user_id: "telegram:1",
    display_name: "Alice",
    tokens_in: 100,
    tokens_out: 200,
    cost_usd: 1.5,
  };

  it("accepts a fully populated row", () => {
    expect(userCostRowSchema.safeParse(valid).success).toBe(true);
  });

  it("accepts a row with a null display_name", () => {
    expect(
      userCostRowSchema.safeParse({ ...valid, display_name: null }).success,
    ).toBe(true);
  });

  it("rejects negative token counts", () => {
    expect(
      userCostRowSchema.safeParse({ ...valid, tokens_in: -1 }).success,
    ).toBe(false);
  });

  it("rejects negative cost_usd", () => {
    expect(
      userCostRowSchema.safeParse({ ...valid, cost_usd: -0.01 }).success,
    ).toBe(false);
  });

  it("rejects a non-integer token count", () => {
    expect(
      userCostRowSchema.safeParse({ ...valid, tokens_out: 10.5 }).success,
    ).toBe(false);
  });
});

describe("perUserCostResponseSchema", () => {
  it("accepts an empty rows array", () => {
    expect(perUserCostResponseSchema.safeParse({ rows: [] }).success).toBe(
      true,
    );
  });

  it("rejects a response without a rows field", () => {
    expect(perUserCostResponseSchema.safeParse({}).success).toBe(false);
  });
});

describe("dailyCostPointSchema + dailyCostResponseSchema", () => {
  it("accepts a valid daily point", () => {
    expect(
      dailyCostPointSchema.safeParse({
        day: "2026-04-15",
        tokens_in: 10,
        tokens_out: 20,
        cost_usd: 0.1,
      }).success,
    ).toBe(true);
  });

  it("wraps daily points in a `{ daily: [] }` envelope", () => {
    expect(dailyCostResponseSchema.safeParse({ daily: [] }).success).toBe(true);
  });
});

describe("sortCostRows", () => {
  const rows = [
    {
      user_id: "telegram:1",
      display_name: "Bob",
      tokens_in: 10,
      tokens_out: 20,
      cost_usd: 2,
    },
    {
      user_id: "telegram:2",
      display_name: "Alice",
      tokens_in: 30,
      tokens_out: 40,
      cost_usd: 5,
    },
    {
      user_id: "telegram:3",
      display_name: null,
      tokens_in: 5,
      tokens_out: 5,
      cost_usd: 1,
    },
  ];

  function ids(result: ReturnType<typeof sortCostRows>) {
    return result.map((r) => r.user_id);
  }

  it("sorts by cost_usd descending", () => {
    expect(ids(sortCostRows(rows, "cost_usd", "desc"))).toEqual([
      "telegram:2",
      "telegram:1",
      "telegram:3",
    ]);
  });

  it("sorts by cost_usd ascending", () => {
    expect(ids(sortCostRows(rows, "cost_usd", "asc"))).toEqual([
      "telegram:3",
      "telegram:1",
      "telegram:2",
    ]);
  });

  it("sorts by display_name using the namespaced id as fallback for nulls", () => {
    // null display_name falls back to "telegram:3" which sorts between
    // "Alice" and "Bob" alphabetically.
    const result = ids(sortCostRows(rows, "display_name", "asc"));
    expect(result[0]).toBe("telegram:2"); // Alice
    expect(result).toContain("telegram:3");
  });

  it("sorts numerically by tokens_in, not lexicographically", () => {
    const twoAndTwenty = [
      { ...rows[0], user_id: "a", tokens_in: 2 },
      { ...rows[0], user_id: "b", tokens_in: 20 },
      { ...rows[0], user_id: "c", tokens_in: 3 },
    ];
    expect(
      sortCostRows(twoAndTwenty, "tokens_in" as PerUserSortKey, "asc").map(
        (r) => r.user_id,
      ),
    ).toEqual(["a", "c", "b"]);
  });

  it("returns a new array (does not mutate input)", () => {
    const original = rows.slice();
    sortCostRows(rows, "cost_usd", "desc");
    expect(rows).toEqual(original);
  });
});
