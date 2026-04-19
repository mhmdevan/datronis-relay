"use client";

import { Badge, Box, Card, Flex, Grid, Text } from "@radix-ui/themes";
import { useTranslations } from "next-intl";
import type { DiskMetrics, RamMetrics, SwapMetrics } from "@/lib/schemas";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(1)} ${units[i]}`;
}

function usageColor(percent: number): "green" | "amber" | "red" {
  if (percent >= 90) return "red";
  if (percent >= 75) return "amber";
  return "green";
}

function ProgressBar({ percent }: { percent: number }) {
  const color = usageColor(percent);
  const colorVar =
    color === "red"
      ? "var(--red-9)"
      : color === "amber"
        ? "var(--amber-9)"
        : "var(--accent-9)";

  return (
    <Box className="w-full h-2 rounded-full bg-[var(--gray-a4)] overflow-hidden">
      <Box
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${Math.min(100, percent)}%`, backgroundColor: colorVar }}
      />
    </Box>
  );
}

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <Flex justify="between" align="center" py="1">
      <Text size="1" color="gray">
        {label}
      </Text>
      <Text size="1" weight="medium">
        {value}
      </Text>
    </Flex>
  );
}

interface ResourceBreakdownProps {
  ram: RamMetrics;
  swap: SwapMetrics;
  disk: DiskMetrics[];
}

export function ResourceBreakdown({ ram, swap, disk }: ResourceBreakdownProps) {
  const t = useTranslations("monitoring");

  return (
    <Grid columns={{ initial: "1", md: "2" }} gap="4">
      {/* RAM detail */}
      <Card>
        <Flex justify="between" align="center" mb="2">
          <Text size="3" weight="bold">
            {t("ram.title")}
          </Text>
          <Badge color={usageColor(ram.usage_percent)}>
            {ram.usage_percent.toFixed(1)}%
          </Badge>
        </Flex>
        <ProgressBar percent={ram.usage_percent} />
        <Box mt="2">
          <DetailRow label={t("ram.total")} value={formatBytes(ram.total_bytes)} />
          <DetailRow label={t("ram.used")} value={formatBytes(ram.used_bytes)} />
          <DetailRow label={t("ram.available")} value={formatBytes(ram.available_bytes)} />
          <DetailRow label={t("ram.buffCache")} value={formatBytes(ram.buff_cache_bytes)} />
          <DetailRow label={t("ram.free")} value={formatBytes(ram.free_bytes)} />
        </Box>
      </Card>

      {/* Swap detail */}
      <Card>
        <Flex justify="between" align="center" mb="2">
          <Text size="3" weight="bold">
            {t("swap.title")}
          </Text>
          <Badge color={swap.total_bytes === 0 ? "gray" : usageColor(swap.usage_percent)}>
            {swap.total_bytes === 0 ? "N/A" : `${swap.usage_percent.toFixed(1)}%`}
          </Badge>
        </Flex>
        <ProgressBar percent={swap.usage_percent} />
        <Box mt="2">
          <DetailRow label={t("swap.total")} value={formatBytes(swap.total_bytes)} />
          <DetailRow label={t("swap.used")} value={formatBytes(swap.used_bytes)} />
          <DetailRow label={t("swap.free")} value={formatBytes(swap.free_bytes)} />
        </Box>
      </Card>

      {/* Disk detail — each filesystem */}
      {disk.map((d) => (
        <Card key={d.mount}>
          <Flex justify="between" align="center" mb="2">
            <Flex direction="column">
              <Text size="3" weight="bold">
                {d.mount}
              </Text>
              <Text size="1" color="gray">
                {d.filesystem}
              </Text>
            </Flex>
            <Badge color={usageColor(d.usage_percent)}>
              {d.usage_percent.toFixed(1)}%
            </Badge>
          </Flex>
          <ProgressBar percent={d.usage_percent} />
          <Box mt="2">
            <DetailRow label={t("disk.total")} value={formatBytes(d.total_bytes)} />
            <DetailRow label={t("disk.used")} value={formatBytes(d.used_bytes)} />
            <DetailRow label={t("disk.available")} value={formatBytes(d.available_bytes)} />
          </Box>
        </Card>
      ))}
    </Grid>
  );
}
