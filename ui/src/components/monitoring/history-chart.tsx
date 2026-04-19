"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Box, Text } from "@radix-ui/themes";
import { useLocale, useTranslations } from "next-intl";
import type { MetricsHistoryPoint } from "@/lib/schemas";

interface HistoryChartProps {
  data: MetricsHistoryPoint[];
  emptyLabel?: string;
}

export function HistoryChart({ data, emptyLabel }: HistoryChartProps) {
  const locale = useLocale();
  const t = useTranslations("monitoring.history");

  const formatted = useMemo(
    () =>
      data.map((p) => ({
        ...p,
        label: new Intl.DateTimeFormat(locale, {
          hour: "numeric",
          minute: "2-digit",
          month: "short",
          day: "numeric",
        }).format(new Date(p.ts)),
      })),
    [data, locale],
  );

  if (data.length === 0) {
    return (
      <Box className="flex h-[300px] items-center justify-center">
        <Text size="2" color="gray">
          {emptyLabel}
        </Text>
      </Box>
    );
  }

  return (
    <Box className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={formatted}
          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--accent-9)" stopOpacity={0.3} />
              <stop offset="95%" stopColor="var(--accent-9)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorRam" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--green-9)" stopOpacity={0.3} />
              <stop offset="95%" stopColor="var(--green-9)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorDisk" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--amber-9)" stopOpacity={0.3} />
              <stop offset="95%" stopColor="var(--amber-9)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorSwap" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--red-9)" stopOpacity={0.3} />
              <stop offset="95%" stopColor="var(--red-9)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--gray-a4)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "var(--gray-11)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--gray-a5)" }}
            interval="preserveStartEnd"
          />
          <YAxis
            width={40}
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: "var(--gray-11)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--gray-a5)" }}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            contentStyle={{
              background: "var(--color-panel-solid)",
              border: "1px solid var(--gray-a5)",
              borderRadius: "var(--radius-3)",
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--gray-12)" }}
            formatter={(value) => [
              `${typeof value === "number" ? value.toFixed(1) : String(value)}%`,
            ]}
          />
          <Legend
            wrapperStyle={{ fontSize: 12 }}
            formatter={(value: string) => (
              <span style={{ color: "var(--gray-11)" }}>{value}</span>
            )}
          />
          <Area
            type="monotone"
            dataKey="cpu_percent"
            name={t("cpu")}
            stroke="var(--accent-9)"
            fillOpacity={1}
            fill="url(#colorCpu)"
            strokeWidth={2}
          />
          <Area
            type="monotone"
            dataKey="ram_percent"
            name={t("ram")}
            stroke="var(--green-9)"
            fillOpacity={1}
            fill="url(#colorRam)"
            strokeWidth={2}
          />
          <Area
            type="monotone"
            dataKey="disk_percent"
            name={t("disk")}
            stroke="var(--amber-9)"
            fillOpacity={1}
            fill="url(#colorDisk)"
            strokeWidth={2}
          />
          <Area
            type="monotone"
            dataKey="swap_percent"
            name={t("swap")}
            stroke="var(--red-9)"
            fillOpacity={1}
            fill="url(#colorSwap)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </Box>
  );
}
