"use client";

import { useState } from "react";
import {
  Box,
  Button,
  Dialog,
  Flex,
  Heading,
  Text,
} from "@radix-ui/themes";
import { PersonIcon, PlusIcon } from "@radix-ui/react-icons";
import { useLocale, useTranslations } from "next-intl";
import { UserTable } from "@/components/users/user-table";
import { UserForm } from "@/components/users/user-form";
import { UserDeleteDialog } from "@/components/users/user-delete-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import type { User, UserFormValues } from "@/lib/schemas";

/**
 * Users list page — Phase UI-1.
 *
 * Handles all four states explicitly (loading, error, empty, success)
 * and drives the Add + Delete dialogs from local state.
 */
export default function UsersPage() {
  const t = useTranslations("users");
  const toast = useToast();
  const locale = useLocale();

  const {
    data: users,
    error,
    isLoading,
    refetch,
    retry,
  } = useApi<User[]>("users.list", (signal) => api.users.list(signal));

  const [addOpen, setAddOpen] = useState(false);
  const [toDelete, setToDelete] = useState<User | null>(null);

  async function handleCreate(values: UserFormValues) {
    try {
      await api.users.create(values);
      toast.success(t("created"));
      setAddOpen(false);
      refetch();
    } catch (err) {
      toast.error(t("createFailed"), errorDetail(err));
      throw err;
    }
  }

  async function handleDelete(user: User) {
    try {
      await api.users.remove(user.id);
      toast.success(t("deleted"));
      refetch();
    } catch (err) {
      toast.error(t("deleteFailed"), errorDetail(err));
    }
  }

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
            <Button>
              <PlusIcon />
              {t("add")}
            </Button>
          </Dialog.Trigger>
          <Dialog.Content maxWidth="520px">
            <Dialog.Title>{t("add")}</Dialog.Title>
            <Dialog.Description size="2" color="gray" mb="4">
              {t("subtitle")}
            </Dialog.Description>
            <UserForm
              submitLabel={t("create")}
              onSubmit={handleCreate}
              onCancel={() => setAddOpen(false)}
            />
          </Dialog.Content>
        </Dialog.Root>
      </Flex>

      {isLoading && <UsersSkeleton />}

      {error && !isLoading && (
        <ErrorState
          title={t("loadError")}
          description={error.message}
          onRetry={retry}
        />
      )}

      {!isLoading && !error && users && users.length === 0 && (
        <EmptyState
          icon={<PersonIcon width={24} height={24} />}
          title={t("empty")}
          description={t("addFirst")}
          action={
            <Button onClick={() => setAddOpen(true)}>
              <PlusIcon />
              {t("add")}
            </Button>
          }
        />
      )}

      {!isLoading && !error && users && users.length > 0 && (
        <UserTable
          users={users}
          onEditHref={(u) => `/${locale}/users/${encodeURIComponent(u.id)}`}
          onDelete={(u) => setToDelete(u)}
        />
      )}

      <UserDeleteDialog
        user={toDelete}
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

function UsersSkeleton() {
  return (
    <Box>
      <Skeleton className="mb-2 h-10 w-full" />
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="mb-2 h-14 w-full" />
      ))}
    </Box>
  );
}
