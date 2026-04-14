"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useLocale } from "next-intl";
import { Box, Text } from "@radix-ui/themes";
import type { DailyCostPoint } from "@/lib/schemas";

/**
 * Daily cost bar chart.
 *
 * - Client component (recharts doesn't render on the server).
 * - `ResponsiveContainer` keeps the chart width-fluid inside its Card.
 * - X-axis ticks are formatted via `Intl.DateTimeFormat` using the active
 *   locale, so the same chart reads correctly in EN/DE/FR/ZH/JA.
 * - Y-axis shows USD with 2 decimals.
 * - Bars use `var(--accent-9)` so they adapt to light/dark and the Radix
 *   accent colour without hard-coding a hex.
 */
export interface CostChartProps {
  data: DailyCostPoint[];
  emptyLabel?: string;
}

export function CostChart({ data, emptyLabel }: CostChartProps) {
  const locale = useLocale();

  const formatted = useMemo(
    () =>
      data.map((point) => ({
        ...point,
        // Pre-format the tick label once to avoid per-render Intl calls.
        label: new Intl.DateTimeFormat(locale, {
          month: "short",
          day: "numeric",
        }).format(new Date(point.day)),
      })),
    [data, locale],
  );

  if (data.length === 0) {
    return (
      <Box className="flex h-[260px] items-center justify-center">
        <Text size="2" color="gray">
          {emptyLabel}
        </Text>
      </Box>
    );
  }

  return (
    <Box className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={formatted}
          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
        >
          <CartesianGrid stroke="var(--gray-a4)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "var(--gray-11)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--gray-a5)" }}
            interval="preserveStartEnd"
          />
          <YAxis
            width={56}
            tick={{ fontSize: 11, fill: "var(--gray-11)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--gray-a5)" }}
            tickFormatter={(v) => `$${Number(v).toFixed(2)}`}
          />
          <Tooltip
            cursor={{ fill: "var(--accent-a3)" }}
            contentStyle={{
              background: "var(--color-panel-solid)",
              border: "1px solid var(--gray-a5)",
              borderRadius: "var(--radius-3)",
              fontSize: 12,
            }}
            formatter={(value) => [
              `$${typeof value === "number" ? value.toFixed(4) : String(value)}`,
              "USD",
            ]}
            labelStyle={{ color: "var(--gray-12)" }}
          />
          <Bar
            dataKey="cost_usd"
            fill="var(--accent-9)"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </Box>
  );
}
