"use client";

import { useState } from "react";
import { Flex, Select, TextField } from "@radix-ui/themes";
import { useTranslations } from "next-intl";
import {
  CUSTOM_KEY,
  INTERVAL_PRESETS,
  findPresetKey,
  type IntervalPresetKey,
} from "@/lib/interval";

/**
 * Preset + custom interval picker.
 *
 * The Phase UI-2 roadmap calls for common presets (30s, 1m, 5m, ...) plus
 * a "custom" escape hatch. Rather than hide complexity, the select shows
 * the human label; when "custom" is chosen, a numeric field appears and
 * the component emits raw seconds via `onChange`.
 *
 * Controlled component: parent owns the `value` (seconds) and reacts to
 * `onChange`. `react-hook-form` wraps this in a `<Controller>`.
 *
 * Presets and helpers live in `lib/interval.ts` so pure tests and table
 * rendering can share them without pulling React.
 */

export interface IntervalSelectProps {
  value: number;
  onChange: (seconds: number) => void;
  /** ARIA label for the select trigger (i18n'd by caller). */
  ariaLabel?: string;
}

export function IntervalSelect({ value, onChange, ariaLabel }: IntervalSelectProps) {
  const t = useTranslations("tasks");

  // `mode` is derived from the initial value but remains sticky afterward:
  // once the user picks "custom", we stay in custom mode even if they type
  // a value that happens to match a preset.
  const [mode, setMode] = useState<IntervalPresetKey | typeof CUSTOM_KEY>(
    () => findPresetKey(value) ?? CUSTOM_KEY,
  );

  function handleSelectChange(next: string) {
    if (next === CUSTOM_KEY) {
      setMode(CUSTOM_KEY);
      return;
    }
    const preset = INTERVAL_PRESETS.find((p) => p.key === next);
    if (!preset) return;
    setMode(preset.key);
    onChange(preset.seconds);
  }

  function handleCustomChange(e: React.ChangeEvent<HTMLInputElement>) {
    const parsed = Number.parseInt(e.target.value, 10);
    onChange(Number.isFinite(parsed) ? parsed : 0);
  }

  return (
    <Flex direction="column" gap="2">
      <Select.Root value={mode} onValueChange={handleSelectChange}>
        <Select.Trigger className="w-full" aria-label={ariaLabel} />
        <Select.Content>
          {INTERVAL_PRESETS.map((preset) => (
            <Select.Item key={preset.key} value={preset.key}>
              {t(`intervals.${preset.key}` as "intervals.1m")}
            </Select.Item>
          ))}
          <Select.Separator />
          <Select.Item value={CUSTOM_KEY}>{t("intervals.custom")}</Select.Item>
        </Select.Content>
      </Select.Root>
      {mode === CUSTOM_KEY && (
        <TextField.Root
          type="number"
          min={1}
          value={value > 0 ? String(value) : ""}
          onChange={handleCustomChange}
          placeholder={t("placeholders.customSeconds")}
          aria-label={t("fields.customSeconds")}
        />
      )}
    </Flex>
  );
}
