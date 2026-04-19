"use client";

import { Badge, Card, Flex, Grid, Text } from "@radix-ui/themes";
import { useTranslations } from "next-intl";
import type { CpuMetrics, DockerInfo, OsInfo } from "@/lib/schemas";

interface SystemInfoCardsProps {
  os: OsInfo;
  cpu: CpuMetrics;
  docker: DockerInfo | null;
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Flex justify="between" align="center" py="1">
      <Text size="2" color="gray">
        {label}
      </Text>
      <Text size="2" weight="medium">
        {value}
      </Text>
    </Flex>
  );
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h ${mins}m`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

export function SystemInfoCards({ os, cpu, docker }: SystemInfoCardsProps) {
  const t = useTranslations("monitoring");

  return (
    <Grid columns={{ initial: "1", sm: "2", lg: "3" }} gap="4">
      {/* OS info */}
      <Card>
        <Text size="3" weight="bold" mb="3" asChild>
          <div>{t("os.title")}</div>
        </Text>
        <Flex direction="column" gap="0">
          <InfoRow label={t("os.hostname")} value={os.hostname} />
          <InfoRow label={t("os.name")} value={os.name} />
          <InfoRow label={t("os.kernel")} value={os.kernel} />
          <InfoRow
            label={t("os.uptime")}
            value={formatUptime(os.uptime_seconds)}
          />
          <InfoRow label={t("os.usersOnline")} value={os.users_online} />
        </Flex>
      </Card>

      {/* CPU info */}
      <Card>
        <Text size="3" weight="bold" mb="3" asChild>
          <div>{t("cpu.title")}</div>
        </Text>
        <Flex direction="column" gap="0">
          <InfoRow label={t("cpu.model")} value={cpu.model} />
          <InfoRow label={t("cpu.cores")} value={cpu.cores} />
          <InfoRow
            label={t("cpu.loadAvg")}
            value={cpu.load_avg.map((v) => v.toFixed(2)).join(" / ")}
          />
          <InfoRow
            label={t("cpu.usage")}
            value={
              <Badge
                color={
                  cpu.usage_percent >= 90
                    ? "red"
                    : cpu.usage_percent >= 75
                      ? "amber"
                      : "green"
                }
              >
                {cpu.usage_percent.toFixed(1)}%
              </Badge>
            }
          />
        </Flex>
      </Card>

      {/* Docker info */}
      <Card>
        <Text size="3" weight="bold" mb="3" asChild>
          <div>{t("docker.title")}</div>
        </Text>
        {docker ? (
          <Flex direction="column" gap="0">
            <InfoRow
              label="Status"
              value={
                <Badge color={docker.running ? "green" : "red"}>
                  {docker.running ? t("docker.running") : t("docker.stopped")}
                </Badge>
              }
            />
            <InfoRow
              label={t("docker.containers")}
              value={docker.containers}
            />
          </Flex>
        ) : (
          <Text size="2" color="gray">
            Docker not detected
          </Text>
        )}
      </Card>
    </Grid>
  );
}
