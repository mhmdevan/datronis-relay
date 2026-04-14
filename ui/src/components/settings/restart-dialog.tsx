"use client";

import { useState } from "react";
import { AlertDialog, Button, Flex } from "@radix-ui/themes";
import { ReloadIcon } from "@radix-ui/react-icons";
import { useTranslations } from "next-intl";

/**
 * Confirmation dialog for restarting the bot.
 *
 * Restart is service-interrupting (cancels in-flight requests), so we
 * gate it behind an `AlertDialog` with an explicit warning. The caller
 * owns `open` + `onOpenChange` and passes an async `onConfirm` — if it
 * rejects, the dialog stays open and the busy spinner clears.
 */
export interface RestartDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<void>;
}

export function RestartDialog({
  open,
  onOpenChange,
  onConfirm,
}: RestartDialogProps) {
  const t = useTranslations("settings");
  const tCommon = useTranslations("common");
  const [busy, setBusy] = useState(false);

  async function handleConfirm() {
    setBusy(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } catch {
      // Parent reports the error via toast; keep the dialog open so the
      // user can retry or cancel.
    } finally {
      setBusy(false);
    }
  }

  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Content maxWidth="460px">
        <AlertDialog.Title>{t("restartConfirmTitle")}</AlertDialog.Title>
        <AlertDialog.Description size="2">
          {t("restartConfirmDescription")}
        </AlertDialog.Description>
        <Flex gap="3" mt="4" justify="end">
          <AlertDialog.Cancel>
            <Button variant="soft" color="gray" disabled={busy}>
              {tCommon("cancel")}
            </Button>
          </AlertDialog.Cancel>
          <Button color="amber" onClick={handleConfirm} loading={busy}>
            <ReloadIcon />
            {t("restartNow")}
          </Button>
        </Flex>
      </AlertDialog.Content>
    </AlertDialog.Root>
  );
}
