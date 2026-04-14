"use client";

import {
  Box,
  Button,
  Dialog,
  Flex,
  Text,
  TextField,
} from "@radix-ui/themes";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useTranslations } from "next-intl";
import {
  tokenRotationFormSchema,
  type AdapterType,
  type TokenRotationFormValues,
} from "@/lib/schemas";

/**
 * Dialog for rotating an adapter's bot token.
 *
 * Fully controlled by the parent (`open` + `onOpenChange`) so the card
 * that triggered it can keep its own local state and show a spinner on
 * the "Rotate" button separately from the dialog's own submit spinner.
 *
 * On success, the parent closes the dialog and refetches adapter state.
 */
export interface TokenRotationDialogProps {
  adapter: AdapterType;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (values: TokenRotationFormValues) => Promise<void>;
}

export function TokenRotationDialog({
  adapter,
  open,
  onOpenChange,
  onSubmit,
}: TokenRotationDialogProps) {
  const t = useTranslations("adapters");
  const tCommon = useTranslations("common");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<TokenRotationFormValues>({
    resolver: zodResolver(tokenRotationFormSchema),
    defaultValues: { token: "" },
  });

  async function handleOk(values: TokenRotationFormValues) {
    await onSubmit(values);
    reset();
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  const adapterLabel = t(adapter as "telegram" | "slack");
  const fieldErrorKey = errors.token?.message;

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Content maxWidth="480px">
        <Dialog.Title>
          {t("rotateTokenTitle", { adapter: adapterLabel })}
        </Dialog.Title>
        <Dialog.Description size="2" color="gray" mb="4">
          {t("rotateTokenDescription")}
        </Dialog.Description>
        <form onSubmit={handleSubmit(handleOk)} noValidate>
          <Box>
            <Text as="label" size="2" weight="medium" htmlFor="new_token">
              {t("newToken")}
            </Text>
            <Box mt="1">
              <TextField.Root
                id="new_token"
                type="password"
                placeholder={t("newTokenPlaceholder")}
                autoComplete="off"
                autoFocus
                {...register("token")}
              />
            </Box>
            {fieldErrorKey && (
              <Text size="1" color="red" mt="1" as="p">
                {tCommon("error")}
              </Text>
            )}
          </Box>
          <Flex gap="2" justify="end" mt="4">
            <Button
              type="button"
              variant="soft"
              color="gray"
              onClick={() => handleOpenChange(false)}
              disabled={isSubmitting}
            >
              {tCommon("cancel")}
            </Button>
            <Button type="submit" loading={isSubmitting}>
              {t("rotateToken")}
            </Button>
          </Flex>
        </form>
      </Dialog.Content>
    </Dialog.Root>
  );
}
