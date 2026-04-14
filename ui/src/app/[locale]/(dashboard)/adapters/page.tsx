"use client";

import { Box, Flex, Grid, Heading, Text } from "@radix-ui/themes";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import { useTranslations } from "next-intl";
import { AdapterCard } from "@/components/adapters/adapter-card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import type {
  AdapterStatus,
  AdapterType,
  TokenRotationFormValues,
} from "@/lib/schemas";

/**
 * Adapters page — Phase UI-2.
 *
 * Renders one `AdapterCard` per adapter the backend reports. All
 * mutations flow through this page so toasts + refetching live in
 * one place, per Phase UI-1's pattern.
 */
export default function AdaptersPage() {
  const t = useTranslations("adapters");
  const toast = useToast();

  const adapters = useApi<AdapterStatus[]>("adapters.list", (signal) =>
    api.adapters.list(signal),
  );

  async function handleToggleEnabled(adapter: AdapterStatus, next: boolean) {
    try {
      await api.adapters.update(adapter.type as AdapterType, {
        enabled: next,
      });
      toast.success(t("updated"));
      adapters.refetch();
    } catch (err) {
      toast.error(t("updateFailed"), errorDetail(err));
      // Propagate so the card's optimistic state can revert.
      throw err;
    }
  }

  async function handleRotateToken(
    adapter: AdapterStatus,
    values: TokenRotationFormValues,
  ) {
    try {
      await api.adapters.update(adapter.type as AdapterType, {
        bot_token: values.token,
      });
      toast.success(t("tokenRotated"));
      adapters.refetch();
    } catch (err) {
      toast.error(t("rotateFailed"), errorDetail(err));
      throw err;
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

      {adapters.isLoading && (
        <Grid columns={{ initial: "1", md: "2" }} gap="4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-56 w-full" />
          ))}
        </Grid>
      )}

      {adapters.error && !adapters.isLoading && (
        <ErrorState
          title={t("loadError")}
          description={adapters.error.message}
          onRetry={adapters.retry}
        />
      )}

      {!adapters.isLoading &&
        !adapters.error &&
        adapters.data &&
        adapters.data.length === 0 && (
          <EmptyState
            icon={<MixerHorizontalIcon width={24} height={24} />}
            title={t("empty")}
          />
        )}

      {!adapters.isLoading &&
        !adapters.error &&
        adapters.data &&
        adapters.data.length > 0 && (
          <Grid columns={{ initial: "1", md: "2" }} gap="4">
            {adapters.data.map((adapter) => (
              <AdapterCard
                key={adapter.type}
                adapter={adapter}
                onToggleEnabled={handleToggleEnabled}
                onRotateToken={handleRotateToken}
              />
            ))}
          </Grid>
        )}
    </Box>
  );
}

function errorDetail(err: unknown): string | undefined {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return undefined;
}
