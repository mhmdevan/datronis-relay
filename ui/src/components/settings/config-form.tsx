"use client";

import {
  Box,
  Button,
  Callout,
  Flex,
  Select,
  Switch,
  Text,
  TextField,
} from "@radix-ui/themes";
import { CheckIcon, InfoCircledIcon } from "@radix-ui/react-icons";
import {
  Controller,
  useForm,
  type Control,
  type FieldPathByValue,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import {
  appConfigSchema,
  logLevelSchema,
  type AppConfig,
  type LogLevel,
} from "@/lib/schemas";
import { ConfigSection } from "@/components/settings/config-section";

/**
 * Settings form — Phase UI-4.
 *
 * Single `react-hook-form` wrapping all 5 config sections. Submit posts
 * the *full* config object (not a partial diff) — the backend endpoint
 * is idempotent and sending the full object avoids server-side merge
 * bugs when both the UI and a human editor touch `config.yaml`.
 *
 * Save button is disabled until the form is dirty. A banner above the
 * actions shows "You have unsaved changes" once any field has been
 * touched, as a visual reinforcement.
 *
 * Validation messages are i18n *keys* (e.g. `"modelRequired"`), resolved
 * by the form against `settings.validation.*` — matches the pattern used
 * in `user-form.tsx` and `task-form.tsx`.
 */

const LOG_LEVELS = logLevelSchema.options;

export interface ConfigFormProps {
  defaultValues: AppConfig;
  onSubmit: (values: AppConfig) => Promise<void>;
  onReset?: () => void;
}

export function ConfigForm({
  defaultValues,
  onSubmit,
  onReset,
}: ConfigFormProps) {
  const t = useTranslations("settings");
  const tCommon = useTranslations("common");

  const {
    control,
    handleSubmit,
    register,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<AppConfig>({
    resolver: zodResolver(appConfigSchema),
    defaultValues,
  });

  /** Resolve a zod error key to a translated message. */
  function fieldError(key: string | undefined): string | undefined {
    if (!key) return undefined;
    return t(`validation.${key}` as "validation.modelRequired");
  }

  function handleResetClick() {
    reset(defaultValues);
    onReset?.();
  }

  async function handleOk(values: AppConfig) {
    await onSubmit(values);
    // Re-seat the form's "pristine" baseline so isDirty becomes false
    // again after a successful save.
    reset(values);
  }

  return (
    <form onSubmit={handleSubmit(handleOk)} noValidate>
      <Flex direction="column" gap="4">
        {/* Claude */}
        <ConfigSection
          title={t("sections.claude.title")}
          description={t("sections.claude.description")}
        >
          <Flex direction="column" gap="3">
            <Field
              label={t("fields.claudeModel")}
              error={fieldError(errors.claude?.model?.message)}
            >
              <TextField.Root
                placeholder="claude-opus-4-6"
                {...register("claude.model")}
              />
            </Field>
            <Field
              label={t("fields.maxTurns")}
              error={fieldError(errors.claude?.max_turns?.message)}
            >
              <TextField.Root
                type="number"
                min={1}
                max={100}
                {...register("claude.max_turns", { valueAsNumber: true })}
              />
            </Field>
          </Flex>
        </ConfigSection>

        {/* Scheduler */}
        <ConfigSection
          title={t("sections.scheduler.title")}
          description={t("sections.scheduler.description")}
        >
          <Flex direction="column" gap="3">
            <SwitchField
              label={t("fields.enabled")}
              control={control}
              name="scheduler.enabled"
            />
            <Field
              label={t("fields.pollInterval")}
              error={fieldError(
                errors.scheduler?.poll_interval_seconds?.message,
              )}
            >
              <TextField.Root
                type="number"
                min={1}
                max={3600}
                {...register("scheduler.poll_interval_seconds", {
                  valueAsNumber: true,
                })}
              />
            </Field>
            <Field
              label={t("fields.maxTasksPerUser")}
              error={fieldError(errors.scheduler?.max_tasks_per_user?.message)}
            >
              <TextField.Root
                type="number"
                min={1}
                max={1000}
                {...register("scheduler.max_tasks_per_user", {
                  valueAsNumber: true,
                })}
              />
            </Field>
          </Flex>
        </ConfigSection>

        {/* Metrics */}
        <ConfigSection
          title={t("sections.metrics.title")}
          description={t("sections.metrics.description")}
        >
          <Flex direction="column" gap="3">
            <SwitchField
              label={t("fields.enabled")}
              control={control}
              name="metrics.enabled"
            />
            <Field
              label={t("fields.metricsHost")}
              error={fieldError(errors.metrics?.host?.message)}
            >
              <TextField.Root
                placeholder="0.0.0.0"
                {...register("metrics.host")}
              />
            </Field>
            <Field
              label={t("fields.metricsPort")}
              error={fieldError(errors.metrics?.port?.message)}
            >
              <TextField.Root
                type="number"
                min={1}
                max={65535}
                {...register("metrics.port", { valueAsNumber: true })}
              />
            </Field>
          </Flex>
        </ConfigSection>

        {/* Attachments */}
        <ConfigSection
          title={t("sections.attachments.title")}
          description={t("sections.attachments.description")}
        >
          <Flex direction="column" gap="3">
            <SwitchField
              label={t("fields.enabled")}
              control={control}
              name="attachments.enabled"
            />
            <Field
              label={t("fields.maxFileSize")}
              error={fieldError(
                errors.attachments?.max_file_size_bytes?.message,
              )}
            >
              <TextField.Root
                type="number"
                min={1}
                {...register("attachments.max_file_size_bytes", {
                  valueAsNumber: true,
                })}
              />
            </Field>
          </Flex>
        </ConfigSection>

        {/* Logging */}
        <ConfigSection
          title={t("sections.logging.title")}
          description={t("sections.logging.description")}
        >
          <Flex direction="column" gap="3">
            <Field
              label={t("fields.logLevel")}
              error={fieldError(errors.logging?.level?.message)}
            >
              <Controller
                control={control}
                name="logging.level"
                render={({ field }) => (
                  <Select.Root
                    value={field.value}
                    onValueChange={(v) => field.onChange(v as LogLevel)}
                  >
                    <Select.Trigger className="w-full" />
                    <Select.Content>
                      {LOG_LEVELS.map((level) => (
                        <Select.Item key={level} value={level}>
                          {t(`logLevels.${level}` as "logLevels.INFO")}
                        </Select.Item>
                      ))}
                    </Select.Content>
                  </Select.Root>
                )}
              />
            </Field>
            <SwitchField
              label={t("fields.logJson")}
              control={control}
              name="logging.json_output"
            />
          </Flex>
        </ConfigSection>

        {isDirty && (
          <Callout.Root color="amber">
            <Callout.Icon>
              <InfoCircledIcon />
            </Callout.Icon>
            <Callout.Text>{t("unsavedChanges")}</Callout.Text>
          </Callout.Root>
        )}

        <Flex gap="2" justify="end">
          <Button
            type="button"
            variant="soft"
            color="gray"
            disabled={!isDirty || isSubmitting}
            onClick={handleResetClick}
          >
            {tCommon("cancel")}
          </Button>
          <Button type="submit" loading={isSubmitting} disabled={!isDirty}>
            <CheckIcon />
            {tCommon("save")}
          </Button>
        </Flex>
      </Flex>
    </form>
  );
}

/** Label + input pair with optional error row. */
function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <Box>
      <Text as="label" size="2" weight="medium">
        {label}
      </Text>
      <Box mt="1">{children}</Box>
      {error && (
        <Text size="1" color="red" mt="1" as="p">
          {error}
        </Text>
      )}
    </Box>
  );
}

/**
 * A boolean field rendered as a Radix Switch, controlled via RHF.
 *
 * Uses `Controller` because `Switch` emits `onCheckedChange`, not the
 * DOM `onChange` event RHF's `register` expects.
 *
 * `FieldPathByValue<AppConfig, boolean>` restricts `name` at the type
 * level to only boolean leaves in the config tree — so a typo like
 * `"claude.model"` is a compile error.
 */
function SwitchField({
  label,
  control,
  name,
}: {
  label: string;
  control: Control<AppConfig>;
  name: FieldPathByValue<AppConfig, boolean>;
}) {
  return (
    <Flex align="center" gap="3">
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <Switch
            checked={!!field.value}
            onCheckedChange={field.onChange}
            aria-label={label}
          />
        )}
      />
      <Text size="2">{label}</Text>
    </Flex>
  );
}
