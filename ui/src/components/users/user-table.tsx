"use client";

import Link from "next/link";
import {
  Badge,
  Code,
  Flex,
  IconButton,
  Table,
  Text,
  Tooltip,
} from "@radix-ui/themes";
import { Pencil1Icon, TrashIcon } from "@radix-ui/react-icons";
import { useLocale, useTranslations } from "next-intl";
import type { User } from "@/lib/schemas";

/**
 * Users table.
 *
 * Presentational — the parent owns the data + mutations. Row actions
 * dispatch callbacks; the parent decides whether to open a dialog,
 * navigate, or fire a mutation.
 */
export interface UserTableProps {
  users: User[];
  onEditHref: (user: User) => string;
  onDelete: (user: User) => void;
}

export function UserTable({ users, onEditHref, onDelete }: UserTableProps) {
  const t = useTranslations("users");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const dateFormatter = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  const numberFormatter = new Intl.NumberFormat(locale);

  return (
    <Table.Root variant="surface">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeaderCell>{t("fields.displayName")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.platform")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.allowedTools")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell align="right">
            {t("fields.ratePerMinute")}
          </Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell align="right">
            {t("fields.ratePerDay")}
          </Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("lastActive")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell align="right">
            {tCommon("actions")}
          </Table.ColumnHeaderCell>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {users.map((user) => {
          const [platform] = user.id.split(":");
          const lastActive = user.last_active_at
            ? dateFormatter.format(new Date(user.last_active_at))
            : t("never");
          return (
            <Table.Row key={user.id} align="center">
              <Table.Cell>
                <Flex direction="column">
                  <Text weight="medium">
                    {user.display_name ?? user.id.split(":")[1]}
                  </Text>
                  <Tooltip content={user.id}>
                    <Code size="1" color="gray" variant="ghost">
                      {user.id}
                    </Code>
                  </Tooltip>
                </Flex>
              </Table.Cell>
              <Table.Cell>
                <PlatformBadge platform={platform} />
              </Table.Cell>
              <Table.Cell>
                <Flex gap="1" wrap="wrap">
                  {user.allowed_tools.map((tool) => (
                    <Badge key={tool} variant="soft" color="indigo">
                      {tool}
                    </Badge>
                  ))}
                </Flex>
              </Table.Cell>
              <Table.Cell align="right">
                <Text>{numberFormatter.format(user.rate_limit_per_minute)}</Text>
              </Table.Cell>
              <Table.Cell align="right">
                <Text>{numberFormatter.format(user.rate_limit_per_day)}</Text>
              </Table.Cell>
              <Table.Cell>
                <Text size="1" color="gray">
                  {lastActive}
                </Text>
              </Table.Cell>
              <Table.Cell align="right">
                <Flex gap="1" justify="end">
                  <Tooltip content={t("edit")}>
                    <IconButton
                      asChild
                      variant="ghost"
                      size="1"
                      aria-label={t("edit")}
                    >
                      <Link href={onEditHref(user)}>
                        <Pencil1Icon />
                      </Link>
                    </IconButton>
                  </Tooltip>
                  <Tooltip content={t("delete")}>
                    <IconButton
                      variant="ghost"
                      color="red"
                      size="1"
                      aria-label={t("delete")}
                      onClick={() => onDelete(user)}
                    >
                      <TrashIcon />
                    </IconButton>
                  </Tooltip>
                </Flex>
              </Table.Cell>
            </Table.Row>
          );
        })}
      </Table.Body>
    </Table.Root>
  );
}

function PlatformBadge({ platform }: { platform: string }) {
  if (platform === "telegram") {
    return <Badge color="blue">Telegram</Badge>;
  }
  if (platform === "slack") {
    return <Badge color="purple">Slack</Badge>;
  }
  return <Badge color="gray">{platform}</Badge>;
}
