"use client";

import { Box, Flex, Text, TextField } from "@radix-ui/themes";

/**
 * Reusable date-range input pair.
 *
 * Uses native `<input type="date">` under the hood so we get free
 * locale-aware rendering, keyboard support, and a platform-native
 * picker — no external date library needed for Phase UI-3.
 *
 * Values are emitted as ISO `YYYY-MM-DD` strings or `undefined` when empty.
 * The parent decides whether to upgrade them to full ISO timestamps or
 * forward as-is to the `/api/audit` endpoint.
 */
export interface DateRangeValue {
  from?: string;
  to?: string;
}

export interface DateRangePickerProps {
  value: DateRangeValue;
  onChange: (next: DateRangeValue) => void;
  labels: { from: string; to: string };
}

export function DateRangePicker({ value, onChange, labels }: DateRangePickerProps) {
  return (
    <Flex gap="3" wrap="wrap">
      <Box>
        <Text as="label" size="1" color="gray" htmlFor="date-range-from">
          {labels.from}
        </Text>
        <Box mt="1">
          <TextField.Root
            id="date-range-from"
            type="date"
            value={value.from ?? ""}
            onChange={(e) =>
              onChange({ ...value, from: emptyToUndefined(e.target.value) })
            }
            max={value.to}
          />
        </Box>
      </Box>
      <Box>
        <Text as="label" size="1" color="gray" htmlFor="date-range-to">
          {labels.to}
        </Text>
        <Box mt="1">
          <TextField.Root
            id="date-range-to"
            type="date"
            value={value.to ?? ""}
            onChange={(e) =>
              onChange({ ...value, to: emptyToUndefined(e.target.value) })
            }
            min={value.from}
          />
        </Box>
      </Box>
    </Flex>
  );
}

function emptyToUndefined(s: string): string | undefined {
  return s === "" ? undefined : s;
}
