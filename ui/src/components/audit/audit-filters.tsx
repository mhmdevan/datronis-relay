"use client";

import { Box, Button, Flex, Select, Text } from "@radix-ui/themes";
import { Cross2Icon } from "@radix-ui/react-icons";
import { useTranslations } from "next-intl";
import {
  DateRangePicker,
  type DateRangeValue,
} from "@/components/ui/date-range-picker";
import type { AuditEventType, User } from "@/lib/schemas";

/**
 * Filter bar for the audit log page.
 *
 * The full filter state is owned by the parent so URL-state and
 * pagination reset logic both live in one place. This component is
 * purely presentational.
 *
 * `"_all"` is a sentinel — Radix `Select.Item` does not allow empty
 * string values, so "no filter" is represented as `"_all"` in the UI
 * and mapped to `undefined` when crossing back into the filter state.
 */

const ALL = "_all" as const;

const EVENT_TYPES: AuditEventType[] = [
  "msg_in",
  "msg_out",
  "auth_fail",
  "rate_limit",
  "claude_ok",
  "claude_error",
];

export interface AuditFilterState {
  eventType?: AuditEventType;
  userId?: string;
  from?: string;
  to?: string;
}

export interface AuditFiltersProps {
  users: User[];
  value: AuditFilterState;
  onChange: (next: AuditFilterState) => void;
}

export function AuditFilters({ users, value, onChange }: AuditFiltersProps) {
  const t = useTranslations("audit");

  function patch(next: Partial<AuditFilterState>) {
    onChange({ ...value, ...next });
  }

  const hasAny =
    value.eventType !== undefined ||
    value.userId !== undefined ||
    value.from !== undefined ||
    value.to !== undefined;

  return (
    <Flex direction="column" gap="3">
      <Flex gap="3" wrap="wrap" align="end">
        {/* Event type */}
        <Box>
          <Text as="label" size="1" color="gray">
            {t("eventType")}
          </Text>
          <Box mt="1">
            <Select.Root
              value={value.eventType ?? ALL}
              onValueChange={(v) =>
                patch({ eventType: v === ALL ? undefined : (v as AuditEventType) })
              }
            >
              <Select.Trigger className="min-w-[180px]" />
              <Select.Content>
                <Select.Item value={ALL}>{t("allEvents")}</Select.Item>
                <Select.Separator />
                {EVENT_TYPES.map((type) => (
                  <Select.Item key={type} value={type}>
                    {t(`events.${type}` as "events.msg_in")}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Box>
        </Box>

        {/* User */}
        <Box>
          <Text as="label" size="1" color="gray">
            {t("filterUser")}
          </Text>
          <Box mt="1">
            <Select.Root
              value={value.userId ?? ALL}
              onValueChange={(v) =>
                patch({ userId: v === ALL ? undefined : v })
              }
            >
              <Select.Trigger className="min-w-[200px]" />
              <Select.Content>
                <Select.Item value={ALL}>{t("allUsers")}</Select.Item>
                <Select.Separator />
                {users.map((u) => (
                  <Select.Item key={u.id} value={u.id}>
                    {u.display_name ?? u.id}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Box>
        </Box>

        {/* Date range */}
        <DateRangePicker
          value={{ from: value.from, to: value.to }}
          onChange={(range: DateRangeValue) =>
            patch({ from: range.from, to: range.to })
          }
          labels={{ from: t("filterFrom"), to: t("filterTo") }}
        />

        {hasAny && (
          <Button
            variant="ghost"
            color="gray"
            size="2"
            onClick={() => onChange({})}
          >
            <Cross2Icon />
            {t("clearFilters")}
          </Button>
        )}
      </Flex>
    </Flex>
  );
}
