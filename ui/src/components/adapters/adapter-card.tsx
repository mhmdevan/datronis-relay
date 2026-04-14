"use client";

import { useState } from "react";
import {
  Badge,
  Button,
  Card,
  Flex,
  Heading,
  Switch,
  Text,
} from "@radix-ui/themes";
import { ReloadIcon } from "@radix-ui/react-icons";
import { useTranslations } from "next-intl";
import { TokenRotationDialog } from "@/components/adapters/token-rotation-dialog";
import type {
  AdapterStatus,
  AdapterType,
  TokenRotationFormValues,
} from "@/lib/schemas";
import { cn } from "@/lib/utils";

/**
 * One-card-per-adapter widget.
 *
 * Visual anchors:
 *   - Status dot (green / gray / red) in the title row summarises health
 *     at a glance without relying on colour alone (text label too).
 *   - Radix `Switch` toggles `enabled` with optimistic UX — on failure
 *     the parent's `refetch` flips it back.
 *   - Rotate button opens `TokenRotationDialog`.
 *
 * All mutations go through callbacks so the page-level toast/refetch
 * logic stays in one place.
 */
export interface AdapterCardProps {
  adapter: AdapterStatus;
  /** Called when the enable/disable switch flips. Rejects => card reverts. */
  onToggleEnabled: (adapter: AdapterStatus, next: boolean) => Promise<void>;
  /** Called on successful token rotation. */
  onRotateToken: (
    adapter: AdapterStatus,
    values: TokenRotationFormValues,
  ) => Promise<void>;
}

export function AdapterCard({
  adapter,
  onToggleEnabled,
  onRotateToken,
}: AdapterCardProps) {
  const t = useTranslations("adapters");

  const [rotateOpen, setRotateOpen] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [optimisticEnabled, setOptimisticEnabled] = useState<boolean | null>(
    null,
  );

  const enabled = optimisticEnabled ?? adapter.enabled;

  async function handleSwitch(next: boolean) {
    setOptimisticEnabled(next);
    setToggling(true);
    try {
      await onToggleEnabled(adapter, next);
      // Parent will refetch and the real prop value wins on next render.
      setOptimisticEnabled(null);
    } catch {
      // Revert local optimism — the parent has already surfaced a toast.
      setOptimisticEnabled(null);
    } finally {
      setToggling(false);
    }
  }

  async function handleRotate(values: TokenRotationFormValues) {
    await onRotateToken(adapter, values);
    setRotateOpen(false);
  }

  const statusKey = statusDot(adapter, enabled);
  const adapterLabel = t(adapter.type as "telegram" | "slack");
  const description = t(`descriptions.${adapter.type}` as "descriptions.telegram");

  return (
    <Card>
      <Flex direction="column" gap="3">
        <Flex justify="between" align="start" gap="3">
          <Flex direction="column" gap="1" className="min-w-0">
            <Flex align="center" gap="2">
              <span
                aria-hidden
                className={cn(
                  "inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full",
                  statusKey === "healthy" && "bg-[var(--green-9)]",
                  statusKey === "idle" && "bg-[var(--gray-8)]",
                  statusKey === "error" && "bg-[var(--red-9)]",
                )}
              />
              <Heading size="4">{adapterLabel}</Heading>
            </Flex>
            <Text size="2" color="gray">
              {description}
            </Text>
          </Flex>
          <Switch
            size="2"
            checked={enabled}
            disabled={toggling}
            onCheckedChange={handleSwitch}
            aria-label={enabled ? t("disable") : t("enable")}
          />
        </Flex>

        <Flex gap="2" wrap="wrap">
          <Badge color={enabled ? "green" : "gray"}>
            {enabled ? t("enabled") : t("disabled")}
          </Badge>
          <Badge color={adapter.healthy ? "green" : "red"} variant="soft">
            {adapter.healthy ? t("healthy") : t("unhealthy")}
          </Badge>
          <Badge color={adapter.token_set ? "indigo" : "amber"} variant="soft">
            {adapter.token_set ? t("tokenSet") : t("tokenMissing")}
          </Badge>
        </Flex>

        {adapter.last_error && (
          <Text size="1" color="red">
            {adapter.last_error}
          </Text>
        )}

        <Flex justify="end" gap="2">
          <Button
            variant="soft"
            color="indigo"
            onClick={() => setRotateOpen(true)}
          >
            <ReloadIcon />
            {t("rotateToken")}
          </Button>
        </Flex>

        <TokenRotationDialog
          adapter={adapter.type as AdapterType}
          open={rotateOpen}
          onOpenChange={setRotateOpen}
          onSubmit={handleRotate}
        />
      </Flex>
    </Card>
  );
}

function statusDot(
  adapter: AdapterStatus,
  enabled: boolean,
): "healthy" | "idle" | "error" {
  if (!enabled) return "idle";
  if (!adapter.healthy) return "error";
  return "healthy";
}
