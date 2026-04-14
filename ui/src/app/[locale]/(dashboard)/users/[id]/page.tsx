"use client";

import { use, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Box, Card, Flex, Heading, IconButton, Text } from "@radix-ui/themes";
import { ArrowLeftIcon } from "@radix-ui/react-icons";
import { useLocale, useTranslations } from "next-intl";
import { UserForm } from "@/components/users/user-form";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { api, ApiError, splitUserId } from "@/lib/api";
import type { User, UserFormValues } from "@/lib/schemas";

/**
 * Edit user page — Phase UI-1.
 *
 * Route: `/[locale]/users/[id]` where `id` is the namespaced user id
 * (url-encoded, e.g. `telegram%3A123456789`).
 */
export default function EditUserPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: encodedId } = use(params);
  const id = decodeURIComponent(encodedId);

  const t = useTranslations("users");
  const tCommon = useTranslations("common");
  const toast = useToast();
  const router = useRouter();
  const locale = useLocale();

  const {
    data: user,
    error,
    isLoading,
    retry,
  } = useApi<User>(`users.get:${id}`, (signal) => api.users.get(id, signal));

  const defaults: Partial<UserFormValues> | undefined = useMemo(() => {
    if (!user) return undefined;
    const { platform, platform_user_id } = splitUserId(user.id);
    return {
      platform,
      platform_user_id,
      display_name: user.display_name ?? "",
      allowed_tools: user.allowed_tools,
      rate_limit_per_minute: user.rate_limit_per_minute,
      rate_limit_per_day: user.rate_limit_per_day,
    };
  }, [user]);

  async function handleSave(values: UserFormValues) {
    try {
      await api.users.update(id, values);
      toast.success(t("updated"));
      router.push(`/${locale}/users`);
    } catch (err) {
      toast.error(t("updateFailed"), errorDetail(err));
      throw err;
    }
  }

  return (
    <Box>
      <Flex align="center" gap="2" mb="4">
        <IconButton variant="ghost" asChild aria-label={tCommon("back")}>
          <Link href={`/${locale}/users`}>
            <ArrowLeftIcon className="rtl:rotate-180" />
          </Link>
        </IconButton>
        <Heading size="6">{t("edit")}</Heading>
      </Flex>

      <Card className="max-w-2xl">
        {isLoading && <EditSkeleton />}

        {!isLoading && error && error.status === 404 && (
          <EmptyState title={t("notFound")} />
        )}

        {!isLoading && error && error.status !== 404 && (
          <ErrorState
            title={t("loadError")}
            description={error.message}
            onRetry={retry}
          />
        )}

        {!isLoading && !error && defaults && (
          <>
            <Text size="2" color="gray" mb="4" as="p">
              {id}
            </Text>
            <UserForm
              defaultValues={defaults}
              submitLabel={t("save")}
              lockIdentity
              onSubmit={handleSave}
              onCancel={() => router.push(`/${locale}/users`)}
            />
          </>
        )}
      </Card>
    </Box>
  );
}

function errorDetail(err: unknown): string | undefined {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return undefined;
}

function EditSkeleton() {
  return (
    <Flex direction="column" gap="4">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-24 w-full" />
      <Flex gap="3">
        <Skeleton className="h-10 flex-1" />
        <Skeleton className="h-10 flex-1" />
      </Flex>
    </Flex>
  );
}
