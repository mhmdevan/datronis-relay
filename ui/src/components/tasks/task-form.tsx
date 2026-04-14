"use client";

import {
  Box,
  Button,
  Callout,
  Flex,
  Select,
  Text,
  TextArea,
  TextField,
} from "@radix-ui/themes";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { useTranslations } from "next-intl";
import { InfoCircledIcon } from "@radix-ui/react-icons";
import { IntervalSelect } from "@/components/ui/interval-select";
import {
  scheduledTaskFormSchema,
  type ScheduledTaskFormValues,
  type User,
} from "@/lib/schemas";

/**
 * Shared scheduled-task form.
 *
 * Used by the "New task" dialog on the tasks page. Follows the same shape
 * as `user-form.tsx` — presentational, zod-validated, emits i18n error keys.
 *
 * `users` is required (not fetched inside the form) so the parent page
 * controls caching and can surface an error if the users list fails to load.
 */

const DEFAULT_VALUES: ScheduledTaskFormValues = {
  user_id: "",
  channel_ref: "",
  prompt: "",
  interval_seconds: 3600, // hourly by default
};

export interface TaskFormProps {
  users: User[];
  defaultValues?: Partial<ScheduledTaskFormValues>;
  submitLabel: string;
  onSubmit: (values: ScheduledTaskFormValues) => Promise<void>;
  onCancel?: () => void;
}

export function TaskForm({
  users,
  defaultValues,
  submitLabel,
  onSubmit,
  onCancel,
}: TaskFormProps) {
  const t = useTranslations("tasks");
  const tCommon = useTranslations("common");

  const {
    control,
    handleSubmit,
    register,
    formState: { errors, isSubmitting },
  } = useForm<ScheduledTaskFormValues>({
    resolver: zodResolver(scheduledTaskFormSchema),
    defaultValues: { ...DEFAULT_VALUES, ...defaultValues },
  });

  /** Look up an i18n error message from a zod error key. */
  function fieldError(key: string | undefined): string | undefined {
    if (!key) return undefined;
    return t(`validation.${key}` as "validation.promptRequired");
  }

  // Guard: if the users list is empty, the form can't collect a valid user.
  // Render a prompt to add a user first rather than a disabled submit button.
  if (users.length === 0) {
    return (
      <Callout.Root color="amber">
        <Callout.Icon>
          <InfoCircledIcon />
        </Callout.Icon>
        <Callout.Text>{t("noUsers")}</Callout.Text>
      </Callout.Root>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <Flex direction="column" gap="4">
        {/* User select */}
        <Box>
          <Text as="label" size="2" weight="medium">
            {t("fields.user")}
          </Text>
          <Box mt="1">
            <Controller
              control={control}
              name="user_id"
              render={({ field }) => (
                <Select.Root
                  value={field.value || undefined}
                  onValueChange={field.onChange}
                >
                  <Select.Trigger
                    className="w-full"
                    placeholder={t("hints.selectUser")}
                  />
                  <Select.Content>
                    {users.map((u) => (
                      <Select.Item key={u.id} value={u.id}>
                        {u.display_name ?? u.id}{" "}
                        <Text size="1" color="gray">
                          ({u.id})
                        </Text>
                      </Select.Item>
                    ))}
                  </Select.Content>
                </Select.Root>
              )}
            />
          </Box>
          {errors.user_id ? (
            <Text size="1" color="red" mt="1" as="p">
              {fieldError(errors.user_id.message)}
            </Text>
          ) : (
            <Text size="1" color="gray" mt="1" as="p">
              {t("hints.selectUser")}
            </Text>
          )}
        </Box>

        {/* Channel reference */}
        <Box>
          <Text as="label" size="2" weight="medium" htmlFor="channel_ref">
            {t("fields.channelRef")}
          </Text>
          <Box mt="1">
            <TextField.Root
              id="channel_ref"
              placeholder={t("placeholders.channelRef")}
              {...register("channel_ref")}
            />
          </Box>
          {errors.channel_ref ? (
            <Text size="1" color="red" mt="1" as="p">
              {fieldError(errors.channel_ref.message)}
            </Text>
          ) : (
            <Text size="1" color="gray" mt="1" as="p">
              {t("hints.channelRef")}
            </Text>
          )}
        </Box>

        {/* Prompt */}
        <Box>
          <Text as="label" size="2" weight="medium" htmlFor="prompt">
            {t("fields.prompt")}
          </Text>
          <Box mt="1">
            <TextArea
              id="prompt"
              rows={4}
              placeholder={t("placeholders.prompt")}
              {...register("prompt")}
            />
          </Box>
          {errors.prompt ? (
            <Text size="1" color="red" mt="1" as="p">
              {fieldError(errors.prompt.message)}
            </Text>
          ) : (
            <Text size="1" color="gray" mt="1" as="p">
              {t("hints.prompt")}
            </Text>
          )}
        </Box>

        {/* Interval */}
        <Box>
          <Text as="label" size="2" weight="medium">
            {t("fields.interval")}
          </Text>
          <Box mt="1">
            <Controller
              control={control}
              name="interval_seconds"
              render={({ field }) => (
                <IntervalSelect
                  value={field.value}
                  onChange={field.onChange}
                  ariaLabel={t("fields.interval")}
                />
              )}
            />
          </Box>
          {errors.interval_seconds && (
            <Text size="1" color="red" mt="1" as="p">
              {fieldError(errors.interval_seconds.message)}
            </Text>
          )}
        </Box>

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
