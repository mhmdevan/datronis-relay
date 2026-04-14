"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Box,
  Button,
  Dialog,
  Flex,
  Heading,
  Text,
} from "@radix-ui/themes";
import { ClockIcon, PlusIcon } from "@radix-ui/react-icons";
import { useLocale, useTranslations } from "next-intl";
import { TaskTable } from "@/components/tasks/task-table";
import { TaskForm } from "@/components/tasks/task-form";
import { TaskDeleteDialog } from "@/components/tasks/task-delete-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import type {
  ScheduledTask,
  ScheduledTaskFormValues,
  User,
} from "@/lib/schemas";

/**
 * Scheduled tasks page — Phase UI-2.
 *
 * Fetches tasks + users in parallel. Tasks drive the table; users power the
 * dropdown in the create form. The create dialog only mounts once the user
 * list has resolved — otherwise the form can't offer a valid selection and
 * we surface a dedicated error banner.
 */
export default function TasksPage() {
  const t = useTranslations("tasks");
  const toast = useToast();
  const locale = useLocale();

  const tasks = useApi<ScheduledTask[]>("tasks.list", (signal) =>
    api.tasks.list(signal),
  );
  const users = useApi<User[]>("users.list", (signal) => api.users.list(signal));

  const [addOpen, setAddOpen] = useState(false);
  const [toDelete, setToDelete] = useState<ScheduledTask | null>(null);

  async function handleCreate(values: ScheduledTaskFormValues) {
    try {
      await api.tasks.create(values);
      toast.success(t("created"));
      setAddOpen(false);
      tasks.refetch();
    } catch (err) {
      toast.error(t("createFailed"), errorDetail(err));
      throw err;
    }
  }

  async function handleToggleActive(task: ScheduledTask) {
    const nextState = !task.is_active;
    try {
      await api.tasks.setActive(task.id, nextState);
      toast.success(nextState ? t("resumed") : t("paused"));
      tasks.refetch();
    } catch (err) {
      toast.error(t("updateFailed"), errorDetail(err));
    }
  }

  async function handleDelete(task: ScheduledTask) {
    try {
      await api.tasks.remove(task.id);
      toast.success(t("deleted"));
      tasks.refetch();
    } catch (err) {
      toast.error(t("deleteFailed"), errorDetail(err));
    }
  }

  const noUsersYet = !!users.data && users.data.length === 0;

  return (
    <Box>
      <Flex justify="between" align="start" gap="4" mb="4" wrap="wrap">
        <Box>
          <Heading size="6">{t("title")}</Heading>
          <Text color="gray" size="2">
            {t("subtitle")}
          </Text>
        </Box>
        <Dialog.Root open={addOpen} onOpenChange={setAddOpen}>
          <Dialog.Trigger>
            <Button disabled={users.isLoading || !!users.error || noUsersYet}>
              <PlusIcon />
              {t("add")}
            </Button>
          </Dialog.Trigger>
          <Dialog.Content maxWidth="560px">
            <Dialog.Title>{t("add")}</Dialog.Title>
            <Dialog.Description size="2" color="gray" mb="4">
              {t("subtitle")}
            </Dialog.Description>
            {users.error && (
              <Box mb="3">
                <ErrorState
                  title={t("usersLoadError")}
                  description={users.error.message}
                  onRetry={users.retry}
                />
              </Box>
            )}
            {users.data && (
              <TaskForm
                users={users.data}
                submitLabel={t("create")}
                onSubmit={handleCreate}
                onCancel={() => setAddOpen(false)}
              />
            )}
          </Dialog.Content>
        </Dialog.Root>
      </Flex>

      {tasks.isLoading && <TasksSkeleton />}

      {tasks.error && !tasks.isLoading && (
        <ErrorState
          title={t("loadError")}
          description={tasks.error.message}
          onRetry={tasks.retry}
        />
      )}

      {!tasks.isLoading &&
        !tasks.error &&
        tasks.data &&
        tasks.data.length === 0 && (
          <EmptyState
            icon={<ClockIcon width={24} height={24} />}
            title={t("empty")}
            description={noUsersYet ? t("noUsers") : t("addFirst")}
            action={
              noUsersYet ? (
                <Button asChild>
                  <Link href={`/${locale}/users`}>
                    <PlusIcon />
                    {t("addFirstUser")}
                  </Link>
                </Button>
              ) : (
                <Button onClick={() => setAddOpen(true)}>
                  <PlusIcon />
                  {t("add")}
                </Button>
              )
            }
          />
        )}

      {!tasks.isLoading &&
        !tasks.error &&
        tasks.data &&
        tasks.data.length > 0 && (
          <TaskTable
            tasks={tasks.data}
            users={users.data ?? []}
            onToggleActive={handleToggleActive}
            onDelete={(task) => setToDelete(task)}
          />
        )}

      <TaskDeleteDialog
        task={toDelete}
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
        onConfirm={handleDelete}
      />
    </Box>
  );
}

function errorDetail(err: unknown): string | undefined {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return undefined;
}

function TasksSkeleton() {
  return (
    <Box>
      <Skeleton className="mb-2 h-10 w-full" />
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="mb-2 h-14 w-full" />
      ))}
    </Box>
  );
}
