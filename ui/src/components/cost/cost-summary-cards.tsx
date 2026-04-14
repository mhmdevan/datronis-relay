"use client";

import { Card, Flex, Grid, Text } from "@radix-ui/themes";
import { useLocale, useTranslations } from "next-intl";
import { Skeleton } from "@/components/ui/skeleton";
import type { CostSummary } from "@/lib/schemas";

/**
 * Four-card summary: today / 7d / 30d / total.
 *
 * Presentational — accepts either `isLoading` (shimmer) or `summary`
 * (rendered values). Errors are handled by the parent, because this
 * component doesn't know the retry handler.
 */
export interface CostSummaryCardsProps {
  summary?: CostSummary;
  isLoading: boolean;
}

export function CostSummaryCards({ summary, isLoading }: CostSummaryCardsProps) {
  const t = useTranslations("cost");
  const locale = useLocale();
  const formatter = new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "USD",
  });

  if (isLoading || !summary) {
    return (
      <Grid columns={{ initial: "1", sm: "2", lg: "4" }} gap="4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </Grid>
    );
  }

  return (
    <Grid columns={{ initial: "1", sm: "2", lg: "4" }} gap="4">
      <SummaryCard label={t("today")} value={formatter.format(summary.today)} />
      <SummaryCard label={t("week")} value={formatter.format(summary.week)} />
      <SummaryCard label={t("month")} value={formatter.format(summary.month)} />
      <SummaryCard label={t("total")} value={formatter.format(summary.total)} />
    </Grid>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
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
