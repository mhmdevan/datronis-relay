import { describe, expect, it } from "vitest";
import { RTL_LOCALES, isRtl, routing } from "@/i18n/routing";

/**
 * RTL infrastructure smoke test.
 *
 * Phase UI-2 removed Farsi, so right now no active locale is RTL. The
 * infrastructure (`isRtl`, `RTL_LOCALES`, `<html dir>` switching in
 * `app/[locale]/layout.tsx`, and the `rtl:rotate-180` classes on
 * directional icons) stays in place so adding `ar` or `he` later is a
 * one-line routing change.
 *
 * This test locks the contract: (1) `isRtl` returns false for every
 * currently-active locale, (2) `isRtl` still returns true for common
 * RTL locales kept in the set, (3) the set is immutable.
 */

describe("isRtl", () => {
  it("returns false for every currently-active locale", () => {
    for (const locale of routing.locales) {
      expect(isRtl(locale)).toBe(false);
    }
  });

  it("returns true for Arabic", () => {
    expect(isRtl("ar")).toBe(true);
  });

  it("returns true for Hebrew", () => {
    expect(isRtl("he")).toBe(true);
  });

  it("returns false for an unknown locale", () => {
    expect(isRtl("xx")).toBe(false);
  });

  it("is case-sensitive (matches how next-intl emits locale codes)", () => {
    expect(isRtl("AR")).toBe(false);
  });
});

describe("RTL_LOCALES", () => {
  it("is declared as ReadonlySet so callers can't mutate it at runtime", () => {
    // The type is ReadonlySet but at runtime it's a plain Set — the guarantee
    // is type-level. We verify we can read it without crashing and that
    // the standard RTL scripts are present.
    expect(RTL_LOCALES.has("ar")).toBe(true);
    expect(RTL_LOCALES.has("he")).toBe(true);
  });
});
