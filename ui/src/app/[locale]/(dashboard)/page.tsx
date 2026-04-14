"use client";

import Link from "next/link";
import {
  Badge,
  Box,
  Button,
  Card,
  Flex,
  Grid,
  Heading,
  Separator,
  Text,
} from "@radix-ui/themes";
import { ClockIcon, PlusIcon } from "@radix-ui/react-icons";
import { useLocale, useTranslations } from "next-intl";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import type { CostSummary, SystemStatus } from "@/lib/schemas";

/**
 * Dashboard home — Phase UI-1.
 *
 * Wired to `/api/status` and `/api/cost/summary` via the `useApi` hook.
 * Those endpoints don't exist yet (Phase UI-5 adds them); for now the
 * page gracefully renders skeletons then the error state so operators
 * can see the shape of the page before the backend is ready.
 */
export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const locale = useLocale();

  const status = useApi<SystemStatus>("system.status", (signal) =>
    api.status.get(signal),
  );
  const cost = useApi<CostSummary>("cost.summary", (signal) =>
    api.cost.summary(signal),
  );

  return (
    <Box>
      <Flex direction="column" gap="1" mb="4">
        <Heading size="6">{t("title")}</Heading>
        <Text color="gray" size="2">
          {t("subtitle")}
        </Text>
      </Flex>

      {/* Status row */}
      <Grid columns={{ initial: "1", sm: "2", lg: "4" }} gap="4" mb="6">
        {status.isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))
        ) : status.error ? (
          <Box className="col-span-full">
            <ErrorState
              title={t("loadError")}
              description={status.error.message}
              onRetry={status.retry}
            />
          </Box>
        ) : status.data ? (
          <>
            <StatusCard
              label={t("version")}
              value={<Text size="4" weight="medium">{status.data.version}</Text>}
            />
            <StatusCard
              label={t("adapters")}
              value={
                <Flex gap="2">
                  <Badge color={status.data.adapters.telegram ? "green" : "gray"}>
                    Telegram
                  </Badge>
                  <Badge color={status.data.adapters.slack ? "green" : "gray"}>
                    Slack
                  </Badge>
                </Flex>
              }
            />
            <StatusCard
              label={t("scheduler")}
              value={
                <Badge color={status.data.scheduler ? "green" : "gray"}>
                  {status.data.scheduler ? t("running") : t("stopped")}
                </Badge>
              }
            />
            <StatusCard
              label={t("uptime")}
              value={
                <Text size="4" weight="medium">
                  {formatUptime(status.data.uptime_seconds)}
                </Text>
              }
            />
          </>
        ) : null}
      </Grid>

      {/* Cost summary */}
      <Grid columns={{ initial: "1", sm: "3" }} gap="4" mb="6">
        {cost.isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))
        ) : cost.error ? (
          <Box className="col-span-full">
            <ErrorState
              title={t("loadError")}
              description={cost.error.message}
              onRetry={cost.retry}
            />
          </Box>
        ) : cost.data ? (
          <>
            <CostCard
              label={t("costToday")}
              value={formatUsd(cost.data.today, locale)}
            />
            <CostCard
              label={t("costWeek")}
              value={formatUsd(cost.data.week, locale)}
            />
            <CostCard
              label={t("costMonth")}
              value={formatUsd(cost.data.month, locale)}
            />
          </>
        ) : null}
      </Grid>

      {/* Quick actions */}
      <Card mb="4">
        <Heading size="3" mb="3">
          {t("quickActions")}
        </Heading>
        <Flex gap="2" wrap="wrap">
          <Button asChild>
            <Link href={`/${locale}/users`}>
              <PlusIcon />
              {t("addUser")}
            </Link>
          </Button>
          <Button asChild variant="soft">
            <Link href={`/${locale}/tasks`}>
              <ClockIcon />
              {t("createTask")}
            </Link>
          </Button>
        </Flex>
      </Card>

      {/* Recent activity */}
      <Card>
        <Heading size="4" mb="3">
          {t("recentActivity")}
        </Heading>
        <Separator size="4" mb="3" />
        <EmptyState title={t("noActivity")} />
      </Card>
    </Box>
  );
}

function StatusCard({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <Card>
      <Flex direction="column" gap="1">
        <Text size="2" color="gray">
          {label}
        </Text>
        {value}
      </Flex>
    </Card>
  );
}

function CostCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <Flex direction="column" gap="1">
        <Text size="2" color="gray">
          {label}
        </Text>
        <Text size="6" weight="bold">
          {value}
        </Text>
      </Flex>
    </Card>
  );
}

function formatUsd(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "USD",
  }).format(value);
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${minutes % 60}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}
