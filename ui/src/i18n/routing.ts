import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "de", "fr", "zh", "ja"],
  defaultLocale: "en",
});

export type Locale = (typeof routing.locales)[number];

/**
 * Locales that use right-to-left text direction.
 *
 * Kept extensible: no current locale is RTL, but the `isRtl` helper and
 * `<html dir>` switching in `app/[locale]/layout.tsx` remain in place so
 * adding `ar` or `he` later is a one-line change here.
 */
export const RTL_LOCALES: ReadonlySet<string> = new Set(["ar", "he"]);

export function isRtl(locale: string): boolean {
  return RTL_LOCALES.has(locale);
}
