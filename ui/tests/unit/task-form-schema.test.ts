import { describe, expect, it } from "vitest";
import { scheduledTaskFormSchema } from "@/lib/schemas";
import { toTaskPayload } from "@/lib/api";

/**
 * Validation contract for the Add task form.
 *
 * The schema emits i18n *keys* (e.g. `"promptRequired"`), not human
 * strings — tests assert on keys so they don't break when translations
 * are reworded.
 */
describe("scheduledTaskFormSchema", () => {
  const valid = {
    user_id: "telegram:123456789",
    channel_ref: "-1001234567890",
    prompt: "Summarize today's error logs",
    interval_seconds: 3600,
  } as const;

  it("accepts a minimal valid payload", () => {
    expect(scheduledTaskFormSchema.safeParse(valid).success).toBe(true);
  });

  it("rejects a blank user_id with userRequired", () => {
    const result = scheduledTaskFormSchema.safeParse({ ...valid, user_id: "" });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("userRequired");
    }
  });

  it("rejects a blank channel_ref with channelRefRequired", () => {
    const result = scheduledTaskFormSchema.safeParse({
      ...valid,
      channel_ref: "",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("channelRefRequired");
    }
  });

  it("rejects a blank prompt with promptRequired", () => {
    const result = scheduledTaskFormSchema.safeParse({ ...valid, prompt: "" });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("promptRequired");
    }
  });

  it("rejects a prompt longer than 4000 characters with promptTooLong", () => {
    const result = scheduledTaskFormSchema.safeParse({
      ...valid,
      prompt: "x".repeat(4001),
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("promptTooLong");
    }
  });

  it("rejects zero interval with intervalPositive", () => {
    const result = scheduledTaskFormSchema.safeParse({
      ...valid,
      interval_seconds: 0,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain("intervalPositive");
    }
  });

  it("rejects a non-integer interval with intervalPositive", () => {
    const result = scheduledTaskFormSchema.safeParse({
      ...valid,
      interval_seconds: 60.5,
    });
    expect(result.success).toBe(false);
  });
});

describe("toTaskPayload", () => {
  it("derives telegram platform from a telegram user id", () => {
    const payload = toTaskPayload({
      user_id: "telegram:123456789",
      channel_ref: "-1001",
      prompt: "hi",
      interval_seconds: 60,
    });
    expect(payload).toEqual({
      user_id: "telegram:123456789",
      platform: "telegram",
      channel_ref: "-1001",
      prompt: "hi",
      interval_seconds: 60,
    });
  });

  it("derives slack platform from a slack user id", () => {
    const payload = toTaskPayload({
      user_id: "slack:U01234567",
      channel_ref: "C01234567",
      prompt: "hi",
      interval_seconds: 300,
    });
    expect(payload.platform).toBe("slack");
  });

  it("falls back to telegram for unknown platform prefixes", () => {
    const payload = toTaskPayload({
      user_id: "unknown:abc",
      channel_ref: "abc",
      prompt: "hi",
      interval_seconds: 60,
    });
    expect(payload.platform).toBe("telegram");
  });
});
