"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  Box,
  Button,
  Card,
  Flex,
  Grid,
  Heading,
  Select,
  Separator,
  Text,
} from "@radix-ui/themes";
import { ReloadIcon } from "@radix-ui/react-icons";
import { useTranslations } from "next-intl";
import { SystemInfoCards } from "@/components/monitoring/system-info-cards";
import { ResourceBreakdown } from "@/components/monitoring/resource-breakdown";
import { NetworkTable } from "@/components/monitoring/network-table";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import type { MetricsHistoryPoint, ServerMetrics } from "@/lib/schemas";

/**
 * Recharts components live in separate chunks — ~115 KB total. Lazy-load
 * them so the monitoring page stays under the 250 KB first-load KPI.
 */
const UsageGauge = dynamic(
  () =>
    import("@/components/monitoring/usage-gauge").then((m) => m.UsageGauge),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[170px] w-[130px]" />,
  },
);

const HistoryChart = dynamic(
  () =>
    import("@/components/monitoring/history-chart").then(
      (m) => m.HistoryChart,
    ),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[300px] w-full" />,
  },
);

const HISTORY_OPTIONS = [
  { key: "last1h", hours: 1 },
  { key: "last6h", hours: 6 },
  { key: "last24h", hours: 24 },
  { key: "last7d", hours: 168 },
] as const;

type HistoryKey = (typeof HISTORY_OPTIONS)[number]["key"];

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export default function MonitoringPage() {
  const t = useTranslations("monitoring");

  const [historyKey, setHistoryKey] = useState<HistoryKey>("last6h");
  const historyHours =
    HISTORY_OPTIONS.find((o) => o.key === historyKey)?.hours ?? 6;

  const metrics = useApi<ServerMetrics>("monitoring.metrics", (signal) =>
    api.monitoring.metrics(signal),
  );

  const history = useApi<MetricsHistoryPoint[]>(
    `monitoring.history:${historyHours}`,
    (signal) => api.monitoring.history(historyHours, signal),
  );

  return (
    <Box>
      {/* Header */}
      <Flex justify="between" align="start" mb="4" wrap="wrap" gap="3">
        <Flex direction="column" gap="1">
          <Heading size="6">{t("title")}</Heading>
          <Text color="gray" size="2">
            {t("subtitle")}
          </Text>
        </Flex>
        <Button
          variant="soft"
          size="2"
          onClick={() => {
            metrics.refetch();
            history.refetch();
          }}
          disabled={metrics.isLoading}
        >
          <ReloadIcon />
          {t("refresh")}
        </Button>
      </Flex>

      {/* Loading state */}
      {metrics.isLoading && (
        <>
          <Grid
            columns={{ initial: "2", sm: "4" }}
            gap="4"
            mb="6"
          >
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-[170px] w-full" />
            ))}
          </Grid>
          <Skeleton className="h-48 w-full mb-4" />
          <Skeleton className="h-64 w-full" />
        </>
      )}

      {/* Error state */}
      {metrics.error && !metrics.isLoading && (
        <ErrorState
          title={t("loadError")}
          description={metrics.error.message}
          onRetry={metrics.retry}
        />
      )}

      {/* Loaded state */}
      {!metrics.isLoading && !metrics.error && metrics.data && (
        <>
          {/* Usage gauges */}
          <Card mb="6">
            <Heading size="4" mb="4">
              {t("sections.usage")}
            </Heading>
            <Flex
              justify="center"
              gap={{ initial: "4", md: "8" }}
              wrap="wrap"
            >
              <UsageGauge
                label={t("cpu.title")}
                percent={metrics.data.cpu.usage_percent}
                subtitle={`${metrics.data.cpu.cores} cores`}
              />
              <UsageGauge
                label={t("ram.title")}
                percent={metrics.data.ram.usage_percent}
                subtitle={`${formatBytes(metrics.data.ram.used_bytes)} / ${formatBytes(metrics.data.ram.total_bytes)}`}
              />
              <UsageGauge
                label={t("disk.title")}
                percent={
                  metrics.data.disk[0]?.usage_percent ?? 0
                }
                subtitle={
                  metrics.data.disk[0]
                    ? `${formatBytes(metrics.data.disk[0].used_bytes)} / ${formatBytes(metrics.data.disk[0].total_bytes)}`
                    : undefined
                }
              />
              <UsageGauge
                label={t("swap.title")}
                percent={metrics.data.swap.usage_percent}
                subtitle={`${formatBytes(metrics.data.swap.used_bytes)} / ${formatBytes(metrics.data.swap.total_bytes)}`}
              />
            </Flex>
          </Card>

          {/* History chart */}
          <Card mb="6">
            <Flex
              justify="between"
              align="center"
              gap="3"
              mb="3"
              wrap="wrap"
            >
              <Heading size="4">{t("sections.history")}</Heading>
              <Select.Root
                value={historyKey}
                onValueChange={(v) => setHistoryKey(v as HistoryKey)}
                size="1"
              >
                <Select.Trigger aria-label={t("history.label")} />
                <Select.Content>
                  {HISTORY_OPTIONS.map((o) => (
                    <Select.Item key={o.key} value={o.key}>
                      {t(`history.${o.key}` as "history.last1h")}
                    </Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </Flex>
            {history.isLoading && <Skeleton className="h-[300px] w-full" />}
            {history.error && !history.isLoading && (
              <ErrorState
                title={t("historyLoadError")}
                description={history.error.message}
                onRetry={history.retry}
              />
            )}
            {!history.isLoading && !history.error && history.data && (
              <HistoryChart
                data={history.data}
                emptyLabel={t("noData")}
              />
            )}
          </Card>

          {/* Resource breakdown */}
          <Box mb="6">
            <Heading size="4" mb="4">
              {t("sections.disk")}
            </Heading>
            <ResourceBreakdown
              ram={metrics.data.ram}
              swap={metrics.data.swap}
              disk={metrics.data.disk}
            />
          </Box>

          {/* System info cards */}
          <Box mb="6">
            <Heading size="4" mb="4">
              {t("sections.overview")}
            </Heading>
            <SystemInfoCards
              os={metrics.data.os}
              cpu={metrics.data.cpu}
              docker={metrics.data.docker}
            />
          </Box>

          {/* Network interfaces */}
          <Box mb="6">
            <NetworkTable interfaces={metrics.data.network} />
          </Box>

          {/* Last updated */}
          <Flex justify="end">
            <Text size="1" color="gray">
              {t("collectedAt")}: {new Date(metrics.data.collected_at).toLocaleString()}
            </Text>
          </Flex>
        </>
      )}
    </Box>
  );
}
