"use client";

import { useEffect, useState } from "react";
import { Box, Button, Card, Flex, Heading, Text } from "@radix-ui/themes";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
} from "@radix-ui/react-icons";
import { useTranslations } from "next-intl";
import {
  AuditFilters,
  type AuditFilterState,
} from "@/components/audit/audit-filters";
import { AuditTable } from "@/components/audit/audit-table";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import type { AuditEntry, User } from "@/lib/schemas";

/**
 * Audit log page — Phase UI-3.
 *
 * Cursor-based pagination stack:
 *   - `cursorStack[-1]` is the cursor for the page currently shown.
 *   - "Next" pushes the server-returned `next_cursor`.
 *   - "Previous" pops the top of the stack.
 *   - Changing any filter resets the stack to `[null]` (first page).
 *
 * Users list is fetched in parallel so the filter dropdown can render
 * human-readable names. If users fail to load, filters still work — just
 * without the friendly names.
 */
const PAGE_SIZE = 50;

interface AuditPayload {
  entries: AuditEntry[];
  next_cursor?: string | null;
}

export default function AuditPage() {
  const t = useTranslations("audit");

  const [filters, setFilters] = useState<AuditFilterState>({});
  const [cursorStack, setCursorStack] = useState<Array<string | null>>([null]);

  // Reset pagination whenever filters change.
  useEffect(() => {
    setCursorStack([null]);
  }, [filters]);

  const currentCursor = cursorStack[cursorStack.length - 1];
  const cacheKey = `audit:${JSON.stringify(filters)}:${currentCursor ?? "_"}`;

  const audit = useApi<AuditPayload>(cacheKey, (signal) =>
    api.audit.list(
      {
        ...filters,
        cursor: currentCursor,
        limit: PAGE_SIZE,
      },
      signal,
    ),
  );
  const users = useApi<User[]>("users.list", (signal) => api.users.list(signal));

  function handleNext() {
    const next = audit.data?.next_cursor;
    if (!next) return;
    setCursorStack((prev) => [...prev, next]);
  }

  function handlePrev() {
    setCursorStack((prev) => (prev.length > 1 ? prev.slice(0, -1) : prev));
  }

  const canPrev = cursorStack.length > 1;
  const canNext = !!audit.data?.next_cursor;

  return (
    <Box>
      <Flex direction="column" gap="1" mb="4">
        <Heading size="6">{t("title")}</Heading>
        <Text color="gray" size="2">
          {t("subtitle")}
        </Text>
      </Flex>

      <Card mb="4">
        <AuditFilters
          users={users.data ?? []}
          value={filters}
          onChange={setFilters}
        />
      </Card>

      {audit.isLoading && <AuditSkeleton />}

      {audit.error && !audit.isLoading && (
        <ErrorState
          title={t("loadError")}
          description={audit.error.message}
          onRetry={audit.retry}
        />
      )}

      {!audit.isLoading &&
        !audit.error &&
        audit.data &&
        audit.data.entries.length === 0 && (
          <EmptyState
            icon={<MagnifyingGlassIcon width={24} height={24} />}
            title={t("empty")}
          />
        )}

      {!audit.isLoading &&
        !audit.error &&
        audit.data &&
        audit.data.entries.length > 0 && (
          <>
            <AuditTable entries={audit.data.entries} users={users.data ?? []} />
            <Flex justify="between" align="center" mt="3">
              <Text size="1" color="gray">
                {audit.data.entries.length} / {PAGE_SIZE}
              </Text>
              <Flex gap="2">
                <Button
                  variant="soft"
                  size="2"
                  disabled={!canPrev}
                  onClick={handlePrev}
                >
                  <ChevronLeftIcon className="rtl:rotate-180" />
                  {t("pagination.previous")}
                </Button>
                <Button
                  variant="soft"
                  size="2"
                  disabled={!canNext}
                  onClick={handleNext}
                >
                  {t("pagination.next")}
                  <ChevronRightIcon className="rtl:rotate-180" />
                </Button>
              </Flex>
            </Flex>
          </>
        )}
    </Box>
  );
}

function AuditSkeleton() {
  return (
    <Box>
      <Skeleton className="mb-2 h-10 w-full" />
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} className="mb-2 h-12 w-full" />
      ))}
    </Box>
  );
}
