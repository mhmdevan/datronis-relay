"use client";

import { useState } from "react";
import { AlertDialog, Button, Flex } from "@radix-ui/themes";
import { useTranslations } from "next-intl";
import type { ScheduledTask } from "@/lib/schemas";

/**
 * Destructive confirmation dialog for task deletion.
 * Mirrors `user-delete-dialog.tsx` — same pattern, task-specific copy.
 */
export interface TaskDeleteDialogProps {
  task: ScheduledTask | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (task: ScheduledTask) => Promise<void>;
}

export function TaskDeleteDialog({
  task,
  open,
  onOpenChange,
  onConfirm,
}: TaskDeleteDialogProps) {
  const t = useTranslations("tasks");
  const tCommon = useTranslations("common");
  const [busy, setBusy] = useState(false);

  async function handleConfirm() {
    if (!task) return;
    setBusy(true);
    try {
      await onConfirm(task);
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Content maxWidth="450px">
        <AlertDialog.Title>{t("deleteTitle")}</AlertDialog.Title>
        <AlertDialog.Description size="2">
          {t("deleteDescription")}
        </AlertDialog.Description>
        <Flex gap="3" mt="4" justify="end">
          <AlertDialog.Cancel>
            <Button variant="soft" color="gray" disabled={busy}>
              {tCommon("cancel")}
            </Button>
          </AlertDialog.Cancel>
          <Button color="red" onClick={handleConfirm} loading={busy}>
            {tCommon("delete")}
          </Button>
        </Flex>
      </AlertDialog.Content>
    </AlertDialog.Root>
  );
}
