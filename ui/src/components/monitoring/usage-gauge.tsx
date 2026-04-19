"use client";

import { useMemo } from "react";
import {
  RadialBarChart,
  RadialBar,
  ResponsiveContainer,
  PolarAngleAxis,
} from "recharts";
import { Box, Flex, Text } from "@radix-ui/themes";

interface UsageGaugeProps {
  label: string;
  percent: number;
  subtitle?: string;
}

function gaugeColor(percent: number): string {
  if (percent >= 90) return "var(--red-9)";
  if (percent >= 75) return "var(--amber-9)";
  return "var(--accent-9)";
}

export function UsageGauge({ label, percent, subtitle }: UsageGaugeProps) {
  const clamped = Math.min(100, Math.max(0, percent));
  const data = useMemo(() => [{ value: clamped }], [clamped]);
  const fill = gaugeColor(clamped);

  return (
    <Flex direction="column" align="center" gap="1">
      <Box className="w-[130px] h-[130px] relative">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="75%"
            outerRadius="100%"
            startAngle={225}
            endAngle={-45}
            data={data}
            barSize={10}
          >
            <PolarAngleAxis
              type="number"
              domain={[0, 100]}
              angleAxisId={0}
              tick={false}
            />
            <RadialBar
              dataKey="value"
              cornerRadius={5}
              fill={fill}
              background={{ fill: "var(--gray-a4)" }}
            />
          </RadialBarChart>
        </ResponsiveContainer>
        <Box className="absolute inset-0 flex items-center justify-center">
          <Text size="5" weight="bold" style={{ color: fill }}>
            {clamped.toFixed(1)}%
          </Text>
        </Box>
      </Box>
      <Text size="2" weight="medium">
        {label}
      </Text>
      {subtitle && (
        <Text size="1" color="gray">
          {subtitle}
        </Text>
      )}
    </Flex>
  );
}
