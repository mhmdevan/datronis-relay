import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations } from "next-intl/server";
import { ThemeProvider } from "next-themes";
import { Theme } from "@radix-ui/themes";

import "@radix-ui/themes/styles.css";
import "@/app/globals.css";
import { isRtl } from "@/i18n/routing";
import { ToastProvider } from "@/components/ui/toast";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app" });
  return {
    title: `${t("title")} — ${t("description")}`,
    description: t("description"),
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const dir = isRtl(locale) ? "rtl" : "ltr";
  const messages = await getMessages({ locale });

  return (
    <html lang={locale} dir={dir} suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <Theme
            accentColor="indigo"
            grayColor="slate"
            radius="medium"
            scaling="100%"
          >
            <NextIntlClientProvider locale={locale} messages={messages}>
              <ToastProvider>{children}</ToastProvider>
            </NextIntlClientProvider>
          </Theme>
        </ThemeProvider>
      </body>
    </html>
  );
}
