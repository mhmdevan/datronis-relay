"use client";

import { useTranslations } from "next-intl";
import { Flex, Heading } from "@radix-ui/themes";
import { ThemeToggle } from "./theme-toggle";
import { LocaleSwitcher } from "./locale-switcher";
import { MobileNav } from "./mobile-nav";

export function Header({ title }: { title?: string }) {
  const t = useTranslations("app");

  return (
    <Flex
      asChild
      align="center"
      justify="between"
      px="4"
      py="3"
      className="border-b border-[var(--gray-a5)] bg-[var(--color-panel)] sticky top-0 z-10"
    >
      <header>
        <Flex align="center" gap="3">
          <MobileNav />
          <Heading size="4" weight="medium">
            {title ?? t("title")}
          </Heading>
        </Flex>

        <Flex align="center" gap="2">
          <LocaleSwitcher />
          <ThemeToggle />
        </Flex>
      </header>
    </Flex>
  );
}
