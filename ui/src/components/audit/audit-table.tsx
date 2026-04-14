"use client";

import { Fragment, useState } from "react";
import {
  Badge,
  Box,
  Code,
  Flex,
  IconButton,
  Table,
  Text,
} from "@radix-ui/themes";
import {
  ChevronDownIcon,
  ChevronRightIcon,
} from "@radix-ui/react-icons";
import { useLocale, useTranslations } from "next-intl";
import type { AuditEntry, AuditEventType, User } from "@/lib/schemas";

/**
 * Audit log table with expandable rows.
 *
 * Radix Themes doesn't ship an expandable-row primitive, so each entry
 * renders as two `<Table.Row>`s: a summary row with a chevron button,
 * and an optional details row that spans all columns. This keeps the
 * semantics of a proper HTML table (useful for screen readers).
 *
 * Expansion state is keyed by correlation_id (unique per entry).
 */
export interface AuditTableProps {
  entries: AuditEntry[];
  users: User[];
}

const EVENT_COLORS: Record<AuditEventType, "gray" | "green" | "red" | "amber" | "blue"> = {
  msg_in: "blue",
  msg_out: "gray",
  auth_fail: "red",
  rate_limit: "amber",
  claude_ok: "green",
  claude_error: "red",
};

export function AuditTable({ entries, users }: AuditTableProps) {
  const t = useTranslations("audit");
  const locale = useLocale();
  const dateFormatter = new Intl.DateTimeFormat(locale, {
    dateStyle: "short",
    timeStyle: "medium",
  });
  const currency = new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 4,
  });

  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggle(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const userById = new Map(users.map((u) => [u.id, u]));

  return (
    <Table.Root variant="surface">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeaderCell width="32px"> </Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.ts")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.eventType")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.user")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.tool")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell align="right">
            {t("fields.cost")}
          </Table.ColumnHeaderCell>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {entries.map((entry) => {
          const isOpen = expanded.has(entry.correlation_id);
          const user = userById.get(entry.user_id);
          const userLabel = user?.display_name ?? entry.user_id;
          return (
            <Fragment key={entry.correlation_id}>
              <Table.Row align="center">
                <Table.Cell>
                  <IconButton
                    size="1"
                    variant="ghost"
                    onClick={() => toggle(entry.correlation_id)}
                    aria-label={isOpen ? t("hideDetails") : t("showDetails")}
                    aria-expanded={isOpen}
                  >
                    {isOpen ? <ChevronDownIcon /> : <ChevronRightIcon />}
                  </IconButton>
                </Table.Cell>
                <Table.Cell>
                  <Text size="1" color="gray">
                    {dateFormatter.format(new Date(entry.ts))}
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  <Badge color={EVENT_COLORS[entry.event_type]}>
                    {t(`events.${entry.event_type}` as "events.msg_in")}
                  </Badge>
                </Table.Cell>
                <Table.Cell>
                  <Text size="2">{userLabel}</Text>
                </Table.Cell>
                <Table.Cell>
                  {entry.tool ? (
                    <Code size="1">{entry.tool}</Code>
                  ) : (
                    <Text color="gray" size="1">
                      —
                    </Text>
                  )}
                </Table.Cell>
                <Table.Cell align="right">
                  {entry.cost_usd != null ? (
                    <Text size="2">{currency.format(entry.cost_usd)}</Text>
                  ) : (
                    <Text color="gray" size="1">
                      —
                    </Text>
                  )}
                </Table.Cell>
              </Table.Row>
              {isOpen && (
                <Table.Row>
                  <Table.Cell colSpan={6}>
                    <AuditDetails entry={entry} />
                  </Table.Cell>
                </Table.Row>
              )}
            </Fragment>
          );
        })}
      </Table.Body>
    </Table.Root>
  );
}

function AuditDetails({ entry }: { entry: AuditEntry }) {
  const t = useTranslations("audit");
  return (
    <Box p="3" className="bg-[var(--gray-a2)] rounded-md">
      <Flex direction="column" gap="2">
        <DetailRow
          label={t("fields.correlationId")}
          value={<Code size="1">{entry.correlation_id}</Code>}
        />
        {entry.command && (
          <DetailRow
            label={t("fields.command")}
            value={<Code size="1">{entry.command}</Code>}
          />
        )}
        {entry.exit_code != null && (
          <DetailRow
            label={t("fields.exitCode")}
            value={<Code size="1">{entry.exit_code}</Code>}
          />
        )}
        {entry.duration_ms != null && (
          <DetailRow
            label={t("fields.duration")}
            value={`${entry.duration_ms} ms`}
          />
        )}
        {entry.tokens_in != null && entry.tokens_out != null && (
          <DetailRow
            label="Tokens"
            value={`${entry.tokens_in} → ${entry.tokens_out}`}
          />
        )}
        {entry.error_category && (
          <DetailRow
            label={t("fields.error")}
            value={
              <Text color="red" size="2">
                {entry.error_category}
              </Text>
            }
          />
        )}
      </Flex>
    </Box>
  );
}

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <Flex gap="3" align="start" wrap="wrap">
      <Text
        size="1"
        color="gray"
        weight="medium"
        className="min-w-[120px] shrink-0"
      >
        {label}
      </Text>
      <Box className="min-w-0 flex-1 break-all">{value}</Box>
    </Flex>
  );
}
