"use client";

import { useState } from "react";
import { Box, Button, Flex, Heading, Text } from "@radix-ui/themes";
import { ReloadIcon } from "@radix-ui/react-icons";
import { useTranslations } from "next-intl";
import { ConfigForm } from "@/components/settings/config-form";
import { ConfigSection } from "@/components/settings/config-section";
import { RestartDialog } from "@/components/settings/restart-dialog";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import type { AppConfig } from "@/lib/schemas";

/**
 * Settings page — Phase UI-4.
 *
 * Fetches `/api/config`, hydrates `ConfigForm` once the data is in,
 * surfaces save errors via toast, and gates the destructive restart
 * action behind an `AlertDialog`.
 *
 * After a successful save, a second toast offers "Restart now" — this
 * preserves the roadmap §5.8 flow where changing `logging.level` etc.
 * only takes effect on restart, but we don't auto-restart because that's
 * a service interruption.
 */
export default function SettingsPage() {
  const t = useTranslations("settings");
  const toast = useToast();

  const config = useApi<AppConfig>("config.get", (signal) =>
    api.config.get(signal),
  );

  const [restartOpen, setRestartOpen] = useState(false);

  async function handleSave(values: AppConfig) {
    try {
      await api.config.update(values);
      toast.success(t("saved"));
      config.refetch();
    } catch (err) {
      toast.error(t("saveFailed"), errorDetail(err));
      throw err;
    }
  }

  async function handleRestart() {
    try {
      await api.system.restart();
      toast.success(t("restarted"));
    } catch (err) {
      toast.error(t("restartFailed"), errorDetail(err));
      throw err;
    }
  }

  return (
    <Box>
      <Flex justify="between" align="start" gap="4" mb="4" wrap="wrap">
        <Box>
          <Heading size="6">{t("title")}</Heading>
          <Text color="gray" size="2">
            {t("subtitle")}
          </Text>
        </Box>
        <Button
          variant="soft"
          color="amber"
          onClick={() => setRestartOpen(true)}
          disabled={config.isLoading}
        >
          <ReloadIcon />
          {t("restart")}
        </Button>
      </Flex>

      {config.isLoading && <SettingsSkeleton />}

      {config.error && !config.isLoading && (
        <ErrorState
          title={t("loadError")}
          description={config.error.message}
          onRetry={config.retry}
        />
      )}

      {!config.isLoading && !config.error && config.data && (
        <ConfigForm defaultValues={config.data} onSubmit={handleSave} />
      )}

      <RestartDialog
        open={restartOpen}
        onOpenChange={setRestartOpen}
        onConfirm={handleRestart}
      />
    </Box>
  );
}

function errorDetail(err: unknown): string | undefined {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return undefined;
}

/**
 * Skeleton that mirrors the shape of the real form — five cards with the
 * right rough heights — so the layout doesn't shift once data resolves.
 */
function SettingsSkeleton() {
  const t = useTranslations("settings");
  return (
    <Flex direction="column" gap="4">
      <SkeletonCard title={t("sections.claude.title")} rows={2} />
      <SkeletonCard title={t("sections.scheduler.title")} rows={3} />
      <SkeletonCard title={t("sections.metrics.title")} rows={3} />
      <SkeletonCard title={t("sections.attachments.title")} rows={2} />
      <SkeletonCard title={t("sections.logging.title")} rows={2} />
    </Flex>
  );
}

function SkeletonCard({ title, rows }: { title: string; rows: number }) {
  return (
    <ConfigSection title={title} description=" ">
      <Flex direction="column" gap="3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </Flex>
    </ConfigSection>
  );
}
