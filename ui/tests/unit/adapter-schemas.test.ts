import { describe, expect, it } from "vitest";
import {
  adapterUpdateSchema,
  tokenRotationFormSchema,
} from "@/lib/schemas";

describe("adapterUpdateSchema", () => {
  it("accepts an `enabled`-only update", () => {
    expect(adapterUpdateSchema.safeParse({ enabled: true }).success).toBe(true);
  });

  it("accepts a `bot_token`-only update", () => {
    expect(
      adapterUpdateSchema.safeParse({ bot_token: "new-token" }).success,
    ).toBe(true);
  });

  it("accepts an `app_token`-only update", () => {
    expect(
      adapterUpdateSchema.safeParse({ app_token: "new-app-token" }).success,
    ).toBe(true);
  });

  it("rejects an empty object with nothingToUpdate", () => {
    const result = adapterUpdateSchema.safeParse({});
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("nothingToUpdate");
    }
  });

  it("rejects an empty-string bot_token with tokenRequired", () => {
    const result = adapterUpdateSchema.safeParse({ bot_token: "" });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("tokenRequired");
    }
  });
});

describe("tokenRotationFormSchema", () => {
  it("accepts a non-empty token", () => {
    expect(tokenRotationFormSchema.safeParse({ token: "abc" }).success).toBe(
      true,
    );
  });

  it("rejects a blank token with tokenRequired", () => {
    const result = tokenRotationFormSchema.safeParse({ token: "" });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("tokenRequired");
    }
  });

  it("rejects a whitespace-only token with tokenRequired", () => {
    const result = tokenRotationFormSchema.safeParse({ token: "   " });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("tokenRequired");
    }
  });
});
