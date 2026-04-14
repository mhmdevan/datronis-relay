"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  Box,
  Button,
  Card,
  Flex,
  Heading,
  Select,
  Text,
} from "@radix-ui/themes";
import { DownloadIcon } from "@radix-ui/react-icons";
import { useTranslations } from "next-intl";
import { CostSummaryCards } from "@/components/cost/cost-summary-cards";
import {
  CostPerUserTable,
  sortCostRows,
  type PerUserSortKey,
} from "@/components/cost/cost-per-user-table";
import { Skeleton as SkeletonLoader } from "@/components/ui/skeleton";

/**
 * The bar chart lives in a separate chunk — recharts is ~115 KB, and
 * loading it eagerly would put `/cost` over the 250 KB first-load KPI.
 * `ssr: false` keeps the server bundle lean and moves it to a lazy
 * client chunk that streams in after hydration.
 */
const CostChart = dynamic(
  () => import("@/components/cost/cost-chart").then((m) => m.CostChart),
  {
    ssr: false,
    loading: () => <SkeletonLoader className="h-[260px] w-full" />,
  },
);
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { downloadCsv, toCsv } from "@/lib/csv";
import type {
  SortDirection,
} from "@/components/ui/sort-header";
import type {
  CostSummary,
  DailyCostPoint,
  UserCostRow,
} from "@/lib/schemas";

/**
 * Cost explorer page — Phase UI-3.
 *
 * Fetches three independent data sources in parallel: summary (for the
 * top cards), daily points (for the chart), and per-user rows (for the
 * sortable table + CSV export). Each has its own loading/error branch
 * so a partial failure still shows the parts that loaded.
 */

const RANGE_OPTIONS: Array<{ key: "last7" | "last14" | "last30" | "last90"; days: number }> = [
  { key: "last7", days: 7 },
  { key: "last14", days: 14 },
  { key: "last30", days: 30 },
  { key: "last90", days: 90 },
];

export default function CostPage() {
  const t = useTranslations("cost");
  const toast = useToast();

  const [rangeKey, setRangeKey] = useState<"last7" | "last14" | "last30" | "last90">("last30");
  const days =
    RANGE_OPTIONS.find((r) => r.key === rangeKey)?.days ?? 30;

  const [sortKey, setSortKey] = useState<PerUserSortKey>("cost_usd");
  const [direction, setDirection] = useState<SortDirection>("desc");

  const summary = useApi<CostSummary>("cost.summary", (signal) =>
    api.cost.summary(signal),
  );
  const daily = useApi<DailyCostPoint[]>(`cost.daily:${days}`, (signal) =>
    api.cost.daily(days, signal),
  );
  const perUser = useApi<UserCostRow[]>("cost.perUser", (signal) =>
    api.cost.perUser(signal),
  );

  function handleSort(key: PerUserSortKey, dir: SortDirection) {
    setSortKey(key);
    setDirection(dir);
  }

  function handleExport() {
    if (!perUser.data) return;
    try {
      const rows = sortCostRows(perUser.data, sortKey, direction);
      const csv = toCsv(rows, [
        { key: "user_id", label: t("fields.user") },
        { key: "display_name", label: "display_name" },
        { key: "tokens_in", label: t("tokensIn") },
        { key: "tokens_out", label: t("tokensOut") },
        {
          key: "cost_usd",
          label: t("costUsd"),
          format: (v) => (typeof v === "number" ? v.toFixed(4) : String(v)),
        },
      ]);
      downloadCsv(`datronis-cost-per-user-${Date.now()}.csv`, csv);
    } catch (err) {
      toast.error(
        t("exportFailed"),
        err instanceof Error ? err.message : undefined,
      );
    }
  }

  return (
    <Box>
      <Flex direction="column" gap="1" mb="4">
        <Heading size="6">{t("title")}</Heading>
        <Text color="gray" size="2">
          {t("subtitle")}
        </Text>
      </Flex>

      {/* Summary cards */}
      <Box mb="4">
        {summary.error ? (
          <ErrorState
            title={t("summaryLoadError")}
            description={summary.error.message}
            onRetry={summary.retry}
          />
        ) : (
          <CostSummaryCards
            summary={summary.data}
            isLoading={summary.isLoading}
          />
        )}
      </Box>

      {/* Daily chart */}
      <Card mb="4">
        <Flex justify="between" align="center" gap="3" mb="3" wrap="wrap">
          <Heading size="4">{t("dailyCost")}</Heading>
          <Select.Root
            value={rangeKey}
            onValueChange={(v) => setRangeKey(v as typeof rangeKey)}
            size="1"
          >
            <Select.Trigger aria-label={t("range.label")} />
            <Select.Content>
              {RANGE_OPTIONS.map((r) => (
                <Select.Item key={r.key} value={r.key}>
                  {t(`range.${r.key}` as "range.last7")}
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Root>
        </Flex>
        {daily.isLoading && <Skeleton className="h-[260px] w-full" />}
        {daily.error && !daily.isLoading && (
          <ErrorState
            title={t("dailyLoadError")}
            description={daily.error.message}
            onRetry={daily.retry}
          />
        )}
        {!daily.isLoading && !daily.error && daily.data && (
          <CostChart data={daily.data} emptyLabel={t("noData")} />
        )}
      </Card>

      {/* Per-user table */}
      <Card>
        <Flex justify="between" align="center" gap="3" mb="3" wrap="wrap">
          <Heading size="4">{t("perUser")}</Heading>
          <Button
            variant="soft"
            size="2"
            onClick={handleExport}
            disabled={!perUser.data || perUser.data.length === 0}
          >
            <DownloadIcon />
            {t("exportCsv")}
          </Button>
        </Flex>

        {perUser.isLoading && <Skeleton className="h-48 w-full" />}

        {perUser.error && !perUser.isLoading && (
          <ErrorState
            title={t("perUserLoadError")}
            description={perUser.error.message}
            onRetry={perUser.retry}
          />
        )}

        {!perUser.isLoading &&
          !perUser.error &&
          perUser.data &&
          perUser.data.length === 0 && <EmptyState title={t("noData")} />}

        {!perUser.isLoading &&
          !perUser.error &&
          perUser.data &&
          perUser.data.length > 0 && (
            <CostPerUserTable
              rows={perUser.data}
              sortKey={sortKey}
              direction={direction}
              onSort={handleSort}
            />
          )}
      </Card>
    </Box>
  );
}
