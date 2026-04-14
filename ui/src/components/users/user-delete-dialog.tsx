"use client";

import { useState } from "react";
import { AlertDialog, Button, Flex } from "@radix-ui/themes";
import { useTranslations } from "next-intl";
import type { User } from "@/lib/schemas";

/**
 * Destructive confirmation dialog for user deletion.
 *
 * The parent passes `open` + `onOpenChange` so it can also drive the
 * dialog from a row-level trigger; `onConfirm` runs the actual delete
 * and swallows its own errors (it reports them via toast at the call site).
 */
export interface UserDeleteDialogProps {
  user: User | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (user: User) => Promise<void>;
}

export function UserDeleteDialog({
  user,
  open,
  onOpenChange,
  onConfirm,
}: UserDeleteDialogProps) {
  const t = useTranslations("users");
  const tCommon = useTranslations("common");
  const [busy, setBusy] = useState(false);

  async function handleConfirm() {
    if (!user) return;
    setBusy(true);
    try {
      await onConfirm(user);
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  }

  const name = user?.display_name ?? user?.id ?? "";

  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Content maxWidth="450px">
        <AlertDialog.Title>{t("deleteTitle")}</AlertDialog.Title>
        <AlertDialog.Description size="2">
          {t("deleteDescription", { name })}
        </AlertDialog.Description>
        <Flex gap="3" mt="4" justify="end">
          <AlertDialog.Cancel>
            <Button variant="soft" color="gray" disabled={busy}>
              {tCommon("cancel")}
            </Button>
          </AlertDialog.Cancel>
          <Button color="red" onClick={handleConfirm} loading={busy}>
            {t("delete")}
          </Button>
        </Flex>
      </AlertDialog.Content>
    </AlertDialog.Root>
  );
}
