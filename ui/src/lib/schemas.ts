/**
 * Zod schemas mirroring the datronis-relay Python backend domain models.
 *
 * These schemas are the single source of truth for API payload validation
 * on the client. They are consumed by `lib/api.ts` (response parsing) and
 * by `react-hook-form` resolvers (form validation).
 *
 * Whenever the Python side changes a field, update it here too — there is
 * no code generation step, so the check lives in tests + runtime parsing.
 */

import { z } from "zod";

// ----------------------------------------------------------------------------
// Primitive aliases
// ----------------------------------------------------------------------------

/** Platform union matching `domain.messages.Platform`. */
export const platformSchema = z.enum(["telegram", "slack", "discord"]);
export type Platform = z.infer<typeof platformSchema>;

/** Tools the user is allowed to invoke via Claude Code. */
export const toolSchema = z.enum(["Read", "Write", "Bash"]);
export type Tool = z.infer<typeof toolSchema>;

// ----------------------------------------------------------------------------
// User
// ----------------------------------------------------------------------------

/**
 * User entity as returned by `GET /api/users`.
 *
 * Matches `domain.user.User` — `id` is always the namespaced form
 * `"<platform>:<platform_uid>"` (e.g. `"telegram:123456789"`).
 */
export const userSchema = z.object({
  id: z.string().min(1),
  display_name: z.string().nullable(),
  allowed_tools: z.array(toolSchema),
  rate_limit_per_minute: z.number().int().positive(),
  rate_limit_per_day: z.number().int().positive(),
  last_active_at: z.string().datetime().nullable().optional(),
});
export type User = z.infer<typeof userSchema>;

/**
 * The form payload used by `user-form.tsx`.
 *
 * The form collects the raw platform + numeric id separately; the API
 * layer combines them into the namespaced id before POST-ing.
 */
export const userFormSchema = z.object({
  platform: platformSchema,
  platform_user_id: z
    .string()
    .min(1, { message: "idRequired" })
    .regex(/^\d+$/, { message: "idNumeric" }),
  display_name: z
    .string()
    .min(1, { message: "nameRequired" })
    .max(64, { message: "nameTooLong" }),
  allowed_tools: z
    .array(toolSchema)
    .min(1, { message: "toolsRequired" }),
  rate_limit_per_minute: z
    .number({ invalid_type_error: "ratePositive" })
    .int()
    .positive({ message: "ratePositive" }),
  rate_limit_per_day: z
    .number({ invalid_type_error: "ratePositive" })
    .int()
    .positive({ message: "ratePositive" }),
});
export type UserFormValues = z.infer<typeof userFormSchema>;

// ----------------------------------------------------------------------------
// Scheduled Task
// ----------------------------------------------------------------------------

export const scheduledTaskSchema = z.object({
  id: z.number().int(),
  user_id: z.string(),
  platform: platformSchema,
  channel_ref: z.string(),
  prompt: z.string(),
  interval_seconds: z.number().int().positive(),
  next_run_at: z.string().datetime(),
  created_at: z.string().datetime(),
  is_active: z.boolean(),
});
export type ScheduledTask = z.infer<typeof scheduledTaskSchema>;

/**
 * Form payload used by `task-form.tsx`.
 *
 * The form collects `user_id` (as the namespaced id of a user pulled from
 * the users list); the API layer derives `platform` by splitting that id
 * before POST-ing to `/api/tasks`.
 *
 * The maximum prompt length (4000) mirrors the Python backend's
 * `messaging.max_text_length` config cap.
 */
export const MAX_TASK_PROMPT_LENGTH = 4000;

export const scheduledTaskFormSchema = z.object({
  user_id: z
    .string()
    .min(1, { message: "userRequired" }),
  channel_ref: z
    .string()
    .min(1, { message: "channelRefRequired" }),
  prompt: z
    .string()
    .min(1, { message: "promptRequired" })
    .max(MAX_TASK_PROMPT_LENGTH, { message: "promptTooLong" }),
  interval_seconds: z
    .number({ invalid_type_error: "intervalPositive" })
    .int()
    .positive({ message: "intervalPositive" }),
});
export type ScheduledTaskFormValues = z.infer<typeof scheduledTaskFormSchema>;

// ----------------------------------------------------------------------------
// Adapter status
// ----------------------------------------------------------------------------

export const adapterTypeSchema = z.enum(["telegram", "slack"]);
export type AdapterType = z.infer<typeof adapterTypeSchema>;

export const adapterStatusSchema = z.object({
  type: adapterTypeSchema,
  enabled: z.boolean(),
  token_set: z.boolean(),
  healthy: z.boolean(),
  last_error: z.string().nullable().optional(),
});
export type AdapterStatus = z.infer<typeof adapterStatusSchema>;

/**
 * Payload for `PUT /api/adapters/:type`.
 *
 * At least one field must be present — an empty object is rejected so
 * callers can't accidentally hit the endpoint without intent. The `bot_token`
 * / `app_token` distinction matches the Python backend: Telegram uses a
 * single bot token; Slack uses both a bot token and an app-level token.
 */
export const adapterUpdateSchema = z
  .object({
    enabled: z.boolean().optional(),
    bot_token: z
      .string()
      .min(1, { message: "tokenRequired" })
      .optional(),
    app_token: z
      .string()
      .min(1, { message: "tokenRequired" })
      .optional(),
  })
  .refine(
    (v) =>
      v.enabled !== undefined ||
      v.bot_token !== undefined ||
      v.app_token !== undefined,
    { message: "nothingToUpdate" },
  );
export type AdapterUpdateValues = z.infer<typeof adapterUpdateSchema>;

/**
 * Form payload used by `token-rotation-dialog.tsx`.
 *
 * A single field is good enough for both Telegram (bot_token) and Slack
 * (bot_token); the app-level token rotation can be added later when
 * Slack app installs actually use it.
 */
export const tokenRotationFormSchema = z.object({
  token: z
    .string()
    .trim()
    .min(1, { message: "tokenRequired" }),
});
export type TokenRotationFormValues = z.infer<typeof tokenRotationFormSchema>;

// ----------------------------------------------------------------------------
// Cost
// ----------------------------------------------------------------------------

export const costSummarySchema = z.object({
  today: z.number(),
  week: z.number(),
  month: z.number(),
  total: z.number(),
  tokens_in: z.number().int(),
  tokens_out: z.number().int(),
});
export type CostSummary = z.infer<typeof costSummarySchema>;

export const dailyCostPointSchema = z.object({
  day: z.string(),
  tokens_in: z.number().int(),
  tokens_out: z.number().int(),
  cost_usd: z.number(),
});
export type DailyCostPoint = z.infer<typeof dailyCostPointSchema>;

/**
 * One row in the per-user cost table.
 *
 * `display_name` is nullable because the backend's `User.display_name` is
 * optional — the UI falls back to `user_id` when it's missing.
 */
export const userCostRowSchema = z.object({
  user_id: z.string(),
  display_name: z.string().nullable().optional(),
  tokens_in: z.number().int().nonnegative(),
  tokens_out: z.number().int().nonnegative(),
  cost_usd: z.number().nonnegative(),
});
export type UserCostRow = z.infer<typeof userCostRowSchema>;

// ----------------------------------------------------------------------------
// Audit
// ----------------------------------------------------------------------------

export const auditEventTypeSchema = z.enum([
  "msg_in",
  "msg_out",
  "auth_fail",
  "rate_limit",
  "claude_ok",
  "claude_error",
]);
export type AuditEventType = z.infer<typeof auditEventTypeSchema>;

export const auditEntrySchema = z.object({
  ts: z.string().datetime(),
  correlation_id: z.string(),
  user_id: z.string(),
  event_type: auditEventTypeSchema,
  tool: z.string().nullable().optional(),
  command: z.string().nullable().optional(),
  exit_code: z.number().int().nullable().optional(),
  duration_ms: z.number().int().nullable().optional(),
  tokens_in: z.number().int().nullable().optional(),
  tokens_out: z.number().int().nullable().optional(),
  cost_usd: z.number().nullable().optional(),
  error_category: z.string().nullable().optional(),
});
export type AuditEntry = z.infer<typeof auditEntrySchema>;

// ----------------------------------------------------------------------------
// System status
// ----------------------------------------------------------------------------

export const systemStatusSchema = z.object({
  version: z.string(),
  uptime_seconds: z.number().int().nonnegative(),
  adapters: z.object({
    telegram: z.boolean(),
    slack: z.boolean(),
  }),
  scheduler: z.boolean(),
});
export type SystemStatus = z.infer<typeof systemStatusSchema>;

// ----------------------------------------------------------------------------
// App config (settings page)
// ----------------------------------------------------------------------------

/**
 * Log levels supported by the Python backend (`logging` module standard).
 * The UI only shows the levels that actually make sense for operators.
 */
export const logLevelSchema = z.enum([
  "DEBUG",
  "INFO",
  "WARNING",
  "ERROR",
  "CRITICAL",
]);
export type LogLevel = z.infer<typeof logLevelSchema>;

/**
 * Form + API schema for the settings page.
 *
 * Mirrors the Python `AppConfig` dataclass tree: nested by section
 * (claude, scheduler, metrics, attachments, logging) so react-hook-form
 * can register fields as dotted paths (`claude.model`, `scheduler.enabled`)
 * and zod emits targeted error messages per leaf.
 *
 * Every field error message is an i18n *key* (e.g. `"modelRequired"`),
 * not a human string, to match the pattern used in earlier phases.
 */

export const claudeConfigSchema = z.object({
  model: z.string().min(1, { message: "modelRequired" }),
  max_turns: z
    .number({ invalid_type_error: "maxTurnsInvalid" })
    .int()
    .min(1, { message: "maxTurnsInvalid" })
    .max(100, { message: "maxTurnsInvalid" }),
});

export const schedulerConfigSchema = z.object({
  enabled: z.boolean(),
  poll_interval_seconds: z
    .number({ invalid_type_error: "pollIntervalInvalid" })
    .int()
    .min(1, { message: "pollIntervalInvalid" })
    .max(3600, { message: "pollIntervalInvalid" }),
  max_tasks_per_user: z
    .number({ invalid_type_error: "maxTasksInvalid" })
    .int()
    .min(1, { message: "maxTasksInvalid" })
    .max(1000, { message: "maxTasksInvalid" }),
});

export const metricsConfigSchema = z.object({
  enabled: z.boolean(),
  host: z.string().min(1, { message: "hostRequired" }),
  port: z
    .number({ invalid_type_error: "portInvalid" })
    .int()
    .min(1, { message: "portInvalid" })
    .max(65535, { message: "portInvalid" }),
});

export const attachmentsConfigSchema = z.object({
  enabled: z.boolean(),
  max_file_size_bytes: z
    .number({ invalid_type_error: "maxFileSizeInvalid" })
    .int()
    .positive({ message: "maxFileSizeInvalid" })
    .max(1_000_000_000, { message: "maxFileSizeInvalid" }),
});

export const loggingConfigSchema = z.object({
  level: logLevelSchema,
  json_output: z.boolean(),
});

export const appConfigSchema = z.object({
  claude: claudeConfigSchema,
  scheduler: schedulerConfigSchema,
  metrics: metricsConfigSchema,
  attachments: attachmentsConfigSchema,
  logging: loggingConfigSchema,
});
export type AppConfig = z.infer<typeof appConfigSchema>;

// ----------------------------------------------------------------------------
// API envelope helpers
// ----------------------------------------------------------------------------

export const usersResponseSchema = z.object({ users: z.array(userSchema) });
export const userResponseSchema = z.object({ user: userSchema });
export const okResponseSchema = z.object({ ok: z.literal(true) });
export const tasksResponseSchema = z.object({
  tasks: z.array(scheduledTaskSchema),
});
export const taskResponseSchema = z.object({ task: scheduledTaskSchema });
export const adaptersResponseSchema = z.object({
  adapters: z.array(adapterStatusSchema),
});
export const adapterResponseSchema = z.object({ adapter: adapterStatusSchema });
export const costSummaryResponseSchema = z.object({
  summary: costSummarySchema,
});
export const dailyCostResponseSchema = z.object({
  daily: z.array(dailyCostPointSchema),
});
export const perUserCostResponseSchema = z.object({
  rows: z.array(userCostRowSchema),
});
export const auditResponseSchema = z.object({
  entries: z.array(auditEntrySchema),
  next_cursor: z.string().nullable().optional(),
});
export const configResponseSchema = z.object({ config: appConfigSchema });
