"use client";

import { useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { IconButton, Box, Flex, Text, Separator } from "@radix-ui/themes";
import {
  ActivityLogIcon,
  BarChartIcon,
  Cross1Icon,
  DashboardIcon,
  GearIcon,
  HamburgerMenuIcon,
  MixIcon,
  PersonIcon,
  ReaderIcon,
  TimerIcon,
} from "@radix-ui/react-icons";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "", labelKey: "dashboard", icon: <DashboardIcon /> },
  { href: "/users", labelKey: "users", icon: <PersonIcon /> },
  { href: "/adapters", labelKey: "adapters", icon: <MixIcon /> },
  { href: "/tasks", labelKey: "tasks", icon: <TimerIcon /> },
  { href: "/cost", labelKey: "cost", icon: <BarChartIcon /> },
  { href: "/monitoring", labelKey: "monitoring", icon: <ActivityLogIcon /> },
  { href: "/audit", labelKey: "audit", icon: <ReaderIcon /> },
  { href: "/settings", labelKey: "settings", icon: <GearIcon /> },
] as const;

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();

  return (
    <Box className="md:hidden">
      <IconButton
        variant="ghost"
        size="2"
        aria-label="Open navigation"
        onClick={() => setOpen(true)}
      >
        <HamburgerMenuIcon />
      </IconButton>

      {open && (
        <>
          {/* Backdrop */}
          <Box
            className="fixed inset-0 z-40 bg-black/50"
            onClick={() => setOpen(false)}
          />

          {/* Drawer */}
          <Box className="fixed inset-y-0 start-0 z-50 w-64 bg-[var(--color-panel)] border-e border-[var(--gray-a5)] p-4">
            <Flex justify="between" align="center" mb="4">
              <Text size="5" weight="bold">
                datronis
              </Text>
              <IconButton
                variant="ghost"
                size="2"
                aria-label="Close navigation"
                onClick={() => setOpen(false)}
              >
                <Cross1Icon />
              </IconButton>
            </Flex>

            <Separator size="4" className="mb-2" />

            <Flex direction="column" gap="1">
              {NAV_ITEMS.map((item) => {
                const fullHref = `/${locale}${item.href}`;
                const isActive =
                  item.href === ""
                    ? pathname === `/${locale}` || pathname === `/${locale}/`
                    : pathname.startsWith(fullHref);

                return (
                  <Link
                    key={item.labelKey}
                    href={fullHref}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                      "hover:bg-[var(--accent-a3)]",
                      isActive
                        ? "bg-[var(--accent-a4)] text-[var(--accent-11)] font-medium"
                        : "text-[var(--gray-11)]"
                    )}
                  >
                    <span className="w-4 h-4 flex-shrink-0">{item.icon}</span>
                    {t(item.labelKey)}
                  </Link>
                );
              })}
            </Flex>
          </Box>
        </>
      )}
    </Box>
  );
}
