"use client";

import { useLocale } from "next-intl";
import { usePathname, useRouter } from "next/navigation";
import { Select } from "@radix-ui/themes";
import { routing, type Locale } from "@/i18n/routing";

const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  de: "Deutsch",
  fr: "Français",
  zh: "中文",
  ja: "日本語",
};

export function LocaleSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  function handleChange(newLocale: string) {
    // Replace the locale segment in the current path.
    // e.g. /en/users → /fa/users
    const segments = pathname.split("/");
    segments[1] = newLocale;
    router.push(segments.join("/"));
  }

  return (
    <Select.Root value={locale} onValueChange={handleChange} size="1">
      <Select.Trigger variant="ghost" />
      <Select.Content>
        {routing.locales.map((loc) => (
          <Select.Item key={loc} value={loc}>
            {LOCALE_LABELS[loc]}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  );
}
