"use client";

import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { useLocale } from "next-intl";
import Link from "next/link";
import { Box, Flex, Text, Separator } from "@radix-ui/themes";
import {
  ActivityLogIcon,
  BarChartIcon,
  DashboardIcon,
  GearIcon,
  MixIcon,
  PersonIcon,
  ReaderIcon,
  TimerIcon,
} from "@radix-ui/react-icons";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  labelKey: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { href: "", labelKey: "dashboard", icon: <DashboardIcon /> },
  { href: "/users", labelKey: "users", icon: <PersonIcon /> },
  { href: "/adapters", labelKey: "adapters", icon: <MixIcon /> },
  { href: "/tasks", labelKey: "tasks", icon: <TimerIcon /> },
  { href: "/cost", labelKey: "cost", icon: <BarChartIcon /> },
  { href: "/monitoring", labelKey: "monitoring", icon: <ActivityLogIcon /> },
  { href: "/audit", labelKey: "audit", icon: <ReaderIcon /> },
  { href: "/settings", labelKey: "settings", icon: <GearIcon /> },
];

export function Sidebar() {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();

  return (
    <Box
      asChild
      className="sidebar-transition hidden md:flex w-60 flex-col border-e border-[var(--gray-a5)] bg-[var(--color-panel)] min-h-screen sticky top-0"
    >
      <nav>
        <Flex direction="column" gap="1" p="4">
          <Text size="5" weight="bold" className="mb-4">
            datronis
          </Text>
          <Separator size="4" className="mb-2" />
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
      </nav>
    </Box>
  );
}
