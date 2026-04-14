"use client";

import {
  Box,
  Button,
  Checkbox,
  Flex,
  Select,
  Text,
  TextField,
} from "@radix-ui/themes";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { useTranslations } from "next-intl";
import { userFormSchema, type Tool, type UserFormValues } from "@/lib/schemas";

/**
 * Shared user form.
 *
 * Used by both the "Add user" dialog and the "Edit user" page, so it
 * stays presentational — the parent decides what to do on submit.
 *
 * Error messages returned by zod are i18n *keys* (e.g. `"idRequired"`),
 * not human strings. This lets the form render the same schema correctly
 * regardless of the active locale. See `lib/schemas.ts` for the key list.
 */

const DEFAULT_VALUES: UserFormValues = {
  platform: "telegram",
  platform_user_id: "",
  display_name: "",
  allowed_tools: ["Read"],
  rate_limit_per_minute: 10,
  rate_limit_per_day: 1000,
};

const ALL_TOOLS: Tool[] = ["Read", "Write", "Bash"];

export interface UserFormProps {
  defaultValues?: Partial<UserFormValues>;
  submitLabel: string;
  onSubmit: (values: UserFormValues) => Promise<void>;
  onCancel?: () => void;
  /** When true, the platform + id fields are locked (editing an existing user). */
  lockIdentity?: boolean;
}

export function UserForm({
  defaultValues,
  submitLabel,
  onSubmit,
  onCancel,
  lockIdentity = false,
}: UserFormProps) {
  const t = useTranslations("users");
  const tCommon = useTranslations("common");

  const {
    control,
    handleSubmit,
    register,
    formState: { errors, isSubmitting },
  } = useForm<UserFormValues>({
    resolver: zodResolver(userFormSchema),
    defaultValues: { ...DEFAULT_VALUES, ...defaultValues },
  });

  /** Look up an i18n error message from a zod error key. */
  function fieldError(key: string | undefined): string | undefined {
    if (!key) return undefined;
    return t(`validation.${key}` as "validation.idRequired");
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <Flex direction="column" gap="4">
        {/* Platform */}
        <Box>
          <Text as="label" size="2" weight="medium">
            {t("fields.platform")}
          </Text>
          <Box mt="1">
            <Controller
              control={control}
              name="platform"
              render={({ field }) => (
                <Select.Root
                  value={field.value}
                  onValueChange={field.onChange}
                  disabled={lockIdentity}
                >
                  <Select.Trigger className="w-full" />
                  <Select.Content>
                    <Select.Item value="telegram">
                      {t("platforms.telegram")}
                    </Select.Item>
                    <Select.Item value="slack">{t("platforms.slack")}</Select.Item>
                  </Select.Content>
                </Select.Root>
              )}
            />
          </Box>
        </Box>

        {/* Platform user id */}
        <Box>
          <Text as="label" size="2" weight="medium" htmlFor="platform_user_id">
            {t("fields.id")}
          </Text>
          <Box mt="1">
            <TextField.Root
              id="platform_user_id"
              placeholder={t("placeholders.id")}
              disabled={lockIdentity}
              {...register("platform_user_id")}
            />
          </Box>
          {errors.platform_user_id ? (
            <Text size="1" color="red" mt="1" as="p">
              {fieldError(errors.platform_user_id.message)}
            </Text>
          ) : (
            <Text size="1" color="gray" mt="1" as="p">
              {t("hints.id")}
            </Text>
          )}
        </Box>

        {/* Display name */}
        <Box>
          <Text as="label" size="2" weight="medium" htmlFor="display_name">
            {t("fields.displayName")}
          </Text>
          <Box mt="1">
            <TextField.Root
              id="display_name"
              placeholder={t("placeholders.displayName")}
              {...register("display_name")}
            />
          </Box>
          {errors.display_name && (
            <Text size="1" color="red" mt="1" as="p">
              {fieldError(errors.display_name.message)}
            </Text>
          )}
        </Box>

        {/* Allowed tools */}
        <Box>
          <Text as="label" size="2" weight="medium">
            {t("fields.allowedTools")}
          </Text>
          <Controller
            control={control}
            name="allowed_tools"
            render={({ field }) => (
              <Flex direction="column" gap="2" mt="2">
                {ALL_TOOLS.map((tool) => {
                  const checked = field.value.includes(tool);
                  return (
                    <Text as="label" size="2" key={tool}>
                      <Flex align="center" gap="2">
                        <Checkbox
                          checked={checked}
                          onCheckedChange={(c) => {
                            if (c) field.onChange([...field.value, tool]);
                            else
                              field.onChange(
                                field.value.filter((v) => v !== tool),
                              );
                          }}
                        />
                        {t(`tools.${tool.toLowerCase()}` as "tools.read")}
                      </Flex>
                    </Text>
                  );
                })}
              </Flex>
            )}
          />
          {errors.allowed_tools ? (
            <Text size="1" color="red" mt="1" as="p">
              {fieldError(
                (errors.allowed_tools as unknown as { message?: string })
                  ?.message,
              )}
            </Text>
          ) : (
            <Text size="1" color="gray" mt="1" as="p">
              {t("hints.allowedTools")}
            </Text>
          )}
        </Box>

        {/* Rate limits */}
        <Flex gap="3">
          <Box className="flex-1">
            <Text as="label" size="2" weight="medium" htmlFor="rpm">
              {t("fields.ratePerMinute")}
            </Text>
            <Box mt="1">
              <TextField.Root
                id="rpm"
                type="number"
                min={1}
                {...register("rate_limit_per_minute", { valueAsNumber: true })}
              />
            </Box>
            {errors.rate_limit_per_minute && (
              <Text size="1" color="red" mt="1" as="p">
                {fieldError(errors.rate_limit_per_minute.message)}
              </Text>
            )}
          </Box>
          <Box className="flex-1">
            <Text as="label" size="2" weight="medium" htmlFor="rpd">
              {t("fields.ratePerDay")}
            </Text>
            <Box mt="1">
              <TextField.Root
                id="rpd"
                type="number"
                min={1}
                {...register("rate_limit_per_day", { valueAsNumber: true })}
              />
            </Box>
            {errors.rate_limit_per_day && (
              <Text size="1" color="red" mt="1" as="p">
                {fieldError(errors.rate_limit_per_day.message)}
              </Text>
            )}
          </Box>
        </Flex>

        {/* Actions */}
        <Flex gap="2" justify="end" mt="2">
          {onCancel && (
            <Button
              type="button"
              variant="soft"
              color="gray"
              onClick={onCancel}
              disabled={isSubmitting}
            >
              {tCommon("cancel")}
            </Button>
          )}
          <Button type="submit" loading={isSubmitting}>
            {submitLabel}
          </Button>
        </Flex>
      </Flex>
    </form>
  );
}
