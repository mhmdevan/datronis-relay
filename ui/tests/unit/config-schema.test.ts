import { describe, expect, it } from "vitest";
import {
  appConfigSchema,
  attachmentsConfigSchema,
  claudeConfigSchema,
  loggingConfigSchema,
  logLevelSchema,
  metricsConfigSchema,
  schedulerConfigSchema,
  type AppConfig,
} from "@/lib/schemas";

/**
 * Validation contract for the settings form.
 *
 * Each section is exercised through its own schema + through the
 * aggregate `appConfigSchema`. Error messages are i18n *keys*
 * (`modelRequired`, `portInvalid`, …) — tests assert on keys so
 * reworded translations don't break the suite.
 */

const VALID_CONFIG: AppConfig = {
  claude: { model: "claude-opus-4-6", max_turns: 10 },
  scheduler: {
    enabled: true,
    poll_interval_seconds: 30,
    max_tasks_per_user: 5,
  },
  metrics: { enabled: true, host: "0.0.0.0", port: 9090 },
  attachments: { enabled: true, max_file_size_bytes: 10_000_000 },
  logging: { level: "INFO", json_output: true },
};

function errorKeys(parse: ReturnType<typeof appConfigSchema.safeParse>): string[] {
  if (parse.success) return [];
  return parse.error.issues.map((i) => i.message);
}

describe("logLevelSchema", () => {
  it("accepts every level from the Python logging module", () => {
    for (const level of ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]) {
      expect(logLevelSchema.safeParse(level).success).toBe(true);
    }
  });

  it("rejects lowercase or unknown levels", () => {
    expect(logLevelSchema.safeParse("info").success).toBe(false);
    expect(logLevelSchema.safeParse("TRACE").success).toBe(false);
  });
});

describe("claudeConfigSchema", () => {
  it("accepts a valid claude section", () => {
    expect(claudeConfigSchema.safeParse(VALID_CONFIG.claude).success).toBe(
      true,
    );
  });

  it("rejects a blank model with modelRequired", () => {
    const result = claudeConfigSchema.safeParse({
      ...VALID_CONFIG.claude,
      model: "",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((i) => i.message)).toContain(
        "modelRequired",
      );
    }
  });

  it("rejects max_turns below 1 with maxTurnsInvalid", () => {
    const result = claudeConfigSchema.safeParse({
      ...VALID_CONFIG.claude,
      max_turns: 0,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((i) => i.message)).toContain(
        "maxTurnsInvalid",
      );
    }
  });

  it("rejects max_turns above 100 with maxTurnsInvalid", () => {
    const result = claudeConfigSchema.safeParse({
      ...VALID_CONFIG.claude,
      max_turns: 101,
    });
    expect(result.success).toBe(false);
  });

  it("rejects a non-integer max_turns", () => {
    const result = claudeConfigSchema.safeParse({
      ...VALID_CONFIG.claude,
      max_turns: 5.5,
    });
    expect(result.success).toBe(false);
  });
});

describe("schedulerConfigSchema", () => {
  it("accepts a valid scheduler section", () => {
    expect(
      schedulerConfigSchema.safeParse(VALID_CONFIG.scheduler).success,
    ).toBe(true);
  });

  it("rejects poll_interval_seconds of 0", () => {
    const result = schedulerConfigSchema.safeParse({
      ...VALID_CONFIG.scheduler,
      poll_interval_seconds: 0,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((i) => i.message)).toContain(
        "pollIntervalInvalid",
      );
    }
  });

  it("rejects poll_interval_seconds above 3600", () => {
    expect(
      schedulerConfigSchema.safeParse({
        ...VALID_CONFIG.scheduler,
        poll_interval_seconds: 3601,
      }).success,
    ).toBe(false);
  });

  it("rejects max_tasks_per_user above 1000 with maxTasksInvalid", () => {
    const result = schedulerConfigSchema.safeParse({
      ...VALID_CONFIG.scheduler,
      max_tasks_per_user: 1001,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((i) => i.message)).toContain(
        "maxTasksInvalid",
      );
    }
  });
});

describe("metricsConfigSchema", () => {
  it("accepts a valid metrics section", () => {
    expect(metricsConfigSchema.safeParse(VALID_CONFIG.metrics).success).toBe(
      true,
    );
  });

  it("rejects a blank host with hostRequired", () => {
    const result = metricsConfigSchema.safeParse({
      ...VALID_CONFIG.metrics,
      host: "",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((i) => i.message)).toContain(
        "hostRequired",
      );
    }
  });

  it("rejects port 0 with portInvalid", () => {
    const result = metricsConfigSchema.safeParse({
      ...VALID_CONFIG.metrics,
      port: 0,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((i) => i.message)).toContain("portInvalid");
    }
  });

  it("rejects port 65536 with portInvalid", () => {
    expect(
      metricsConfigSchema.safeParse({ ...VALID_CONFIG.metrics, port: 65536 })
        .success,
    ).toBe(false);
  });

  it("accepts port 65535 (max valid)", () => {
    expect(
      metricsConfigSchema.safeParse({ ...VALID_CONFIG.metrics, port: 65535 })
        .success,
    ).toBe(true);
  });
});

describe("attachmentsConfigSchema", () => {
  it("accepts a valid attachments section", () => {
    expect(
      attachmentsConfigSchema.safeParse(VALID_CONFIG.attachments).success,
    ).toBe(true);
  });

  it("rejects a negative max_file_size_bytes", () => {
    const result = attachmentsConfigSchema.safeParse({
      ...VALID_CONFIG.attachments,
      max_file_size_bytes: -1,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((i) => i.message)).toContain(
        "maxFileSizeInvalid",
      );
    }
  });

  it("rejects a zero max_file_size_bytes", () => {
    expect(
      attachmentsConfigSchema.safeParse({
        ...VALID_CONFIG.attachments,
        max_file_size_bytes: 0,
      }).success,
    ).toBe(false);
  });
});

describe("loggingConfigSchema", () => {
  it("accepts a valid logging section", () => {
    expect(loggingConfigSchema.safeParse(VALID_CONFIG.logging).success).toBe(
      true,
    );
  });

  it("rejects an unknown log level", () => {
    expect(
      loggingConfigSchema.safeParse({
        level: "TRACE",
        json_output: false,
      }).success,
    ).toBe(false);
  });
});

describe("appConfigSchema (aggregate)", () => {
  it("accepts a fully valid config", () => {
    expect(appConfigSchema.safeParse(VALID_CONFIG).success).toBe(true);
  });

  it("collects errors from multiple sections", () => {
    const broken = {
      ...VALID_CONFIG,
      claude: { model: "", max_turns: 200 },
      metrics: { enabled: true, host: "", port: 99999 },
    };
    const result = appConfigSchema.safeParse(broken);
    expect(result.success).toBe(false);
    const keys = errorKeys(result);
    expect(keys).toContain("modelRequired");
    expect(keys).toContain("maxTurnsInvalid");
    expect(keys).toContain("hostRequired");
    expect(keys).toContain("portInvalid");
  });

  it("rejects a config missing a whole section", () => {
    const { logging: _drop, ...rest } = VALID_CONFIG;
    void _drop;
    expect(appConfigSchema.safeParse(rest).success).toBe(false);
  });
});
