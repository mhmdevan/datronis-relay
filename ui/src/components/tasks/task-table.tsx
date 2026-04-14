"use client";

import {
  Badge,
  Flex,
  IconButton,
  Table,
  Text,
  Tooltip,
} from "@radix-ui/themes";
import { PauseIcon, PlayIcon, TrashIcon } from "@radix-ui/react-icons";
import { useLocale, useTranslations } from "next-intl";
import type { ScheduledTask, User } from "@/lib/schemas";
import { formatCustomSeconds, intervalLabelKey } from "@/lib/interval";

/**
 * Scheduled tasks table.
 *
 * Presentational: receives `tasks` + `users` (so it can resolve display
 * names instead of raw ids) and dispatches row actions through callbacks.
 * The parent owns the mutations and their toast/error handling.
 */

export interface TaskTableProps {
  tasks: ScheduledTask[];
  users: User[];
  onToggleActive: (task: ScheduledTask) => void;
  onDelete: (task: ScheduledTask) => void;
}

export function TaskTable({
  tasks,
  users,
  onToggleActive,
  onDelete,
}: TaskTableProps) {
  const t = useTranslations("tasks");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const dateFormatter = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  const userById = new Map(users.map((u) => [u.id, u]));

  return (
    <Table.Root variant="surface">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeaderCell>{t("fields.user")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.platform")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.prompt")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.interval")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.nextRun")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>{t("fields.status")}</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell align="right">
            {tCommon("actions")}
          </Table.ColumnHeaderCell>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {tasks.map((task) => {
          const user = userById.get(task.user_id);
          const displayName = user?.display_name ?? task.user_id;
          const intervalKey = intervalLabelKey(task.interval_seconds);
          const isCustom = intervalKey === "intervals.custom";
          return (
            <Table.Row key={task.id} align="center">
              <Table.Cell>
                <Flex direction="column">
                  <Text weight="medium">{displayName}</Text>
                  <Text size="1" color="gray">
                    {task.user_id}
                  </Text>
                </Flex>
              </Table.Cell>
              <Table.Cell>
                <PlatformBadge platform={task.platform} />
              </Table.Cell>
              <Table.Cell>
                <Tooltip content={task.prompt}>
                  <Text size="2" className="line-clamp-2 max-w-[240px]">
                    {task.prompt}
                  </Text>
                </Tooltip>
              </Table.Cell>
              <Table.Cell>
                <Text>
                  {isCustom
                    ? formatCustomSeconds(task.interval_seconds)
                    : t(intervalKey as "intervals.1m")}
                </Text>
              </Table.Cell>
              <Table.Cell>
                <Text size="1" color="gray">
                  {dateFormatter.format(new Date(task.next_run_at))}
                </Text>
              </Table.Cell>
              <Table.Cell>
                {task.is_active ? (
                  <Badge color="green">{t("statusActive")}</Badge>
                ) : (
                  <Badge color="gray">{t("statusPaused")}</Badge>
                )}
              </Table.Cell>
              <Table.Cell align="right">
                <Flex gap="1" justify="end">
                  <Tooltip
                    content={task.is_active ? t("pause") : t("resume")}
                  >
                    <IconButton
                      variant="ghost"
                      size="1"
                      aria-label={task.is_active ? t("pause") : t("resume")}
                      onClick={() => onToggleActive(task)}
                    >
                      {task.is_active ? <PauseIcon /> : <PlayIcon />}
                    </IconButton>
                  </Tooltip>
                  <Tooltip content={tCommon("delete")}>
                    <IconButton
                      variant="ghost"
                      color="red"
                      size="1"
                      aria-label={tCommon("delete")}
                      onClick={() => onDelete(task)}
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
  if (platform === "telegram") return <Badge color="blue">Telegram</Badge>;
  if (platform === "slack") return <Badge color="purple">Slack</Badge>;
  return <Badge color="gray">{platform}</Badge>;
}
