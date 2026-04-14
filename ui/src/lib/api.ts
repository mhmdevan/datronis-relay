/**
 * Typed fetch wrapper for the datronis-relay REST API.
 *
 * Every public helper:
 *   1. Builds the URL against `/api/...` (rewritten by next.config.ts to
 *      the Python backend in dev, served by the same origin in prod).
 *   2. Adds the `Authorization: Bearer <token>` header from localStorage.
 *   3. Parses the JSON body through a zod schema — any shape drift from
 *      the Python backend surfaces as a `ApiError` instead of crashing
 *      somewhere deep in a component tree.
 *   4. Throws a structured `ApiError` on non-2xx responses.
 *
 * The API endpoints themselves don't exist yet — Phase UI-5 adds them
 * to the Python backend. Until then, `fetchJson` will fail at runtime,
 * but the call sites are already wired so the swap is zero-work.
 */

import { z } from "zod";
import {
  adapterResponseSchema,
  adaptersResponseSchema,
  auditResponseSchema,
  configResponseSchema,
  costSummaryResponseSchema,
  dailyCostResponseSchema,
  okResponseSchema,
  perUserCostResponseSchema,
  systemStatusSchema,
  taskResponseSchema,
  tasksResponseSchema,
  userResponseSchema,
  usersResponseSchema,
  type AdapterType,
  type AdapterUpdateValues,
  type AppConfig,
  type AuditEventType,
  type ScheduledTaskFormValues,
  type User,
  type UserFormValues,
} from "./schemas";

const AUTH_STORAGE_KEY = "datronis-token";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/** Read the stored bearer token. Safe to call on the server. */
function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_STORAGE_KEY);
}

interface FetchOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
  signal?: AbortSignal;
}

/**
 * Core fetch primitive. Validates the response against the given zod schema.
 *
 * @throws ApiError on any non-2xx status, network failure, or schema mismatch.
 */
export async function fetchJson<T>(
  path: string,
  schema: z.ZodType<T>,
  options: FetchOptions = {},
): Promise<T> {
  const { method = "GET", body, signal } = options;
  const token = getAuthToken();

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "network_error", (err as Error).message);
  }

  if (response.status === 401) {
    // Token expired or missing — kick the user back to /login.
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
      const locale = window.location.pathname.split("/")[1] || "en";
      window.location.href = `/${locale}/login`;
    }
    throw new ApiError(401, "unauthorized", "Session expired");
  }

  if (!response.ok) {
    let code = `http_${response.status}`;
    let message = response.statusText || "Request failed";
    try {
      const errorBody = (await response.json()) as {
        code?: string;
        message?: string;
      };
      if (errorBody.code) code = errorBody.code;
      if (errorBody.message) message = errorBody.message;
    } catch {
      // Body was not JSON — fall through with defaults.
    }
    throw new ApiError(response.status, code, message);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch (err) {
    throw new ApiError(
      response.status,
      "invalid_json",
      `Malformed JSON response: ${(err as Error).message}`,
    );
  }

  const result = schema.safeParse(payload);
  if (!result.success) {
    throw new ApiError(
      response.status,
      "schema_mismatch",
      "Unexpected response shape",
      result.error.flatten(),
    );
  }
  return result.data;
}

// ----------------------------------------------------------------------------
// Endpoint helpers — one per REST route.
// ----------------------------------------------------------------------------

/**
 * Convert the form's separate platform + numeric id into the namespaced id
 * the Python backend expects: `"<platform>:<platform_uid>"`.
 */
function toUserPayload(values: UserFormValues) {
  return {
    id: `${values.platform}:${values.platform_user_id}`,
    display_name: values.display_name,
    allowed_tools: values.allowed_tools,
    rate_limit_per_minute: values.rate_limit_per_minute,
    rate_limit_per_day: values.rate_limit_per_day,
  };
}

/**
 * Given a user row, split the namespaced id back into its parts so the
 * edit form can pre-fill the platform select and the numeric-id field.
 */
export function splitUserId(id: string): {
  platform: "telegram" | "slack" | "discord";
  platform_user_id: string;
} {
  const [platformRaw, ...rest] = id.split(":");
  const platform =
    platformRaw === "telegram" || platformRaw === "slack" || platformRaw === "discord"
      ? platformRaw
      : "telegram";
  return { platform, platform_user_id: rest.join(":") };
}

/**
 * Convert the task form's `{ user_id, channel_ref, prompt, interval_seconds }`
 * into the POST body the Python backend expects.
 *
 * `platform` is derived from the namespaced user id so the form never needs
 * a separate platform picker — the selected user's platform is authoritative.
 */
/**
 * Serialize a flat record into a `?a=1&b=2` query string, skipping any
 * `undefined`, `null`, or empty-string values.
 *
 * Exported so unit tests can exercise the skip rules — the rest of the
 * client uses it indirectly through the `api.*` helpers.
 */
export function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    const str = String(value);
    if (str === "") continue;
    usp.append(key, str);
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

/**
 * Parameters accepted by `/api/audit`. All are optional; the backend
 * treats missing fields as "no filter".
 */
export interface AuditListParams {
  eventType?: AuditEventType;
  userId?: string;
  from?: string;
  to?: string;
  cursor?: string | null;
  limit?: number;
}

export function toTaskPayload(values: ScheduledTaskFormValues) {
  const { platform } = splitUserId(values.user_id);
  return {
    user_id: values.user_id,
    platform,
    channel_ref: values.channel_ref,
    prompt: values.prompt,
    interval_seconds: values.interval_seconds,
  };
}

export const api = {
  status: {
    get: (signal?: AbortSignal) =>
      fetchJson("/api/status", systemStatusSchema, { signal }),
  },
  system: {
    restart: () =>
      fetchJson("/api/restart", okResponseSchema, { method: "POST" }),
  },
  config: {
    get: (signal?: AbortSignal) =>
      fetchJson("/api/config", configResponseSchema, { signal }).then(
        (r) => r.config,
      ),
    update: (values: AppConfig) =>
      fetchJson("/api/config", configResponseSchema, {
        method: "PUT",
        body: values,
      }).then((r) => r.config),
  },
  users: {
    list: (signal?: AbortSignal) =>
      fetchJson("/api/users", usersResponseSchema, { signal }).then(
        (r) => r.users,
      ),
    get: async (id: string, signal?: AbortSignal): Promise<User> => {
      const { users } = await fetchJson("/api/users", usersResponseSchema, {
        signal,
      });
      const user = users.find((u) => u.id === id);
      if (!user) {
        throw new ApiError(404, "not_found", `User ${id} not found`);
      }
      return user;
    },
    create: (values: UserFormValues) =>
      fetchJson("/api/users", userResponseSchema, {
        method: "POST",
        body: toUserPayload(values),
      }).then((r) => r.user),
    update: (id: string, values: UserFormValues) =>
      fetchJson(`/api/users/${encodeURIComponent(id)}`, userResponseSchema, {
        method: "PUT",
        body: toUserPayload(values),
      }).then((r) => r.user),
    remove: (id: string) =>
      fetchJson(`/api/users/${encodeURIComponent(id)}`, okResponseSchema, {
        method: "DELETE",
      }),
  },
  adapters: {
    list: (signal?: AbortSignal) =>
      fetchJson("/api/adapters", adaptersResponseSchema, { signal }).then(
        (r) => r.adapters,
      ),
    update: (type: AdapterType, values: AdapterUpdateValues) =>
      fetchJson(`/api/adapters/${type}`, adapterResponseSchema, {
        method: "PUT",
        body: values,
      }).then((r) => r.adapter),
  },
  tasks: {
    list: (signal?: AbortSignal) =>
      fetchJson("/api/tasks", tasksResponseSchema, { signal }).then(
        (r) => r.tasks,
      ),
    create: (values: ScheduledTaskFormValues) =>
      fetchJson("/api/tasks", taskResponseSchema, {
        method: "POST",
        body: toTaskPayload(values),
      }).then((r) => r.task),
    setActive: (id: number, isActive: boolean) =>
      fetchJson(`/api/tasks/${id}`, taskResponseSchema, {
        method: "PUT",
        body: { is_active: isActive },
      }).then((r) => r.task),
    remove: (id: number) =>
      fetchJson(`/api/tasks/${id}`, okResponseSchema, {
        method: "DELETE",
      }),
  },
  cost: {
    summary: (signal?: AbortSignal) =>
      fetchJson("/api/cost/summary", costSummaryResponseSchema, { signal }).then(
        (r) => r.summary,
      ),
    daily: (days: number, signal?: AbortSignal) =>
      fetchJson(
        `/api/cost/daily${buildQuery({ days })}`,
        dailyCostResponseSchema,
        { signal },
      ).then((r) => r.daily),
    perUser: (signal?: AbortSignal) =>
      fetchJson(
        "/api/cost/by-user",
        perUserCostResponseSchema,
        { signal },
      ).then((r) => r.rows),
  },
  audit: {
    list: (params: AuditListParams = {}, signal?: AbortSignal) =>
      fetchJson(
        `/api/audit${buildQuery({
          event_type: params.eventType,
          user_id: params.userId,
          from: params.from,
          to: params.to,
          cursor: params.cursor ?? undefined,
          limit: params.limit,
        })}`,
        auditResponseSchema,
        { signal },
      ),
  },
};
