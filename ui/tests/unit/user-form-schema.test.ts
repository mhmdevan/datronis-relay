import { describe, expect, it } from "vitest";
import { userFormSchema } from "@/lib/schemas";
import { splitUserId } from "@/lib/api";

/**
 * Validation contract for the Add/Edit user form.
 *
 * The human-facing strings live in the i18n locale files; the schema
 * only emits *keys* (e.g. `"idRequired"`), so tests assert on keys.
 */
describe("userFormSchema", () => {
  const validPayload = {
    platform: "telegram",
    platform_user_id: "123456789",
    display_name: "Alice",
    allowed_tools: ["Read"],
    rate_limit_per_minute: 10,
    rate_limit_per_day: 1000,
  } as const;

  it("accepts a minimal valid payload", () => {
    expect(userFormSchema.safeParse(validPayload).success).toBe(true);
  });

  it("rejects a blank user id with idRequired", () => {
    const result = userFormSchema.safeParse({
      ...validPayload,
      platform_user_id: "",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("idRequired");
    }
  });

  it("rejects a non-numeric user id with idNumeric", () => {
    const result = userFormSchema.safeParse({
      ...validPayload,
      platform_user_id: "alice",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("idNumeric");
    }
  });

  it("rejects an empty tool list with toolsRequired", () => {
    const result = userFormSchema.safeParse({
      ...validPayload,
      allowed_tools: [],
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("toolsRequired");
    }
  });

  it("rejects zero or negative rate limits with ratePositive", () => {
    const result = userFormSchema.safeParse({
      ...validPayload,
      rate_limit_per_minute: 0,
      rate_limit_per_day: -1,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("ratePositive");
    }
  });

  it("rejects names longer than 64 characters with nameTooLong", () => {
    const result = userFormSchema.safeParse({
      ...validPayload,
      display_name: "x".repeat(65),
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("nameTooLong");
    }
  });
});

describe("splitUserId", () => {
  it("splits a telegram user id", () => {
    expect(splitUserId("telegram:123456789")).toEqual({
      platform: "telegram",
      platform_user_id: "123456789",
    });
  });

  it("splits a slack user id", () => {
    expect(splitUserId("slack:U01234567")).toEqual({
      platform: "slack",
      platform_user_id: "U01234567",
    });
  });

  it("defaults unknown platforms to telegram", () => {
    expect(splitUserId("unknown:abc")).toEqual({
      platform: "telegram",
      platform_user_id: "abc",
    });
  });
});
