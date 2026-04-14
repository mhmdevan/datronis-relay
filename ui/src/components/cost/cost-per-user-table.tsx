"use client";

import { useMemo } from "react";
import { Code, Table, Text } from "@radix-ui/themes";
import { useLocale, useTranslations } from "next-intl";
import {
  SortHeader,
  type SortDirection,
} from "@/components/ui/sort-header";
import type { UserCostRow } from "@/lib/schemas";

/**
 * Sortable per-user cost table.
 *
 * The parent owns `{ sortKey, direction }` and passes `onSort` so the
 * tests or a URL-state hook can control sorting without re-implementing it.
 * Sorting itself is done here (pure, in-memory) because the dataset is
 * small — per-user rows scale with the number of configured users.
 */
export type PerUserSortKey =
  | "display_name"
  | "tokens_in"
  | "tokens_out"
  | "cost_usd";

export interface CostPerUserTableProps {
  rows: UserCostRow[];
  sortKey: PerUserSortKey;
  direction: SortDirection;
  onSort: (key: PerUserSortKey, direction: SortDirection) => void;
}

/**
 * Pure sort helper — exported for unit tests.
 *
 * Numbers sort numerically; the user name column falls back to the
 * namespaced id when `display_name` is null, matching how the UI renders.
 */
export function sortCostRows(
  rows: readonly UserCostRow[],
  key: PerUserSortKey,
  direction: SortDirection,
): UserCostRow[] {
  const copy = rows.slice();
  const factor = direction === "desc" ? -1 : 1;
  copy.sort((a, b) => {
    if (key === "display_name") {
      const aName = a.display_name ?? a.user_id;
      const bName = b.display_name ?? b.user_id;
      return aName.localeCompare(bName) * factor;
    }
    return (a[key] - b[key]) * factor;
  });
  return copy;
}

export function CostPerUserTable({
  rows,
  sortKey,
  direction,
  onSort,
}: CostPerUserTableProps) {
  const t = useTranslations("cost");
  const locale = useLocale();
  const currency = new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "USD",
  });
  const number = new Intl.NumberFormat(locale);

  const sorted = useMemo(
    () => sortCostRows(rows, sortKey, direction),
    [rows, sortKey, direction],
  );

  return (
    <Table.Root variant="surface">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeaderCell>
            <SortHeader
              columnKey="display_name"
              label={t("fields.user")}
              activeKey={sortKey}
              direction={direction}
              onSort={onSort}
            />
          </Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell align="right">
            <SortHeader
              columnKey="tokens_in"
              label={t("tokensIn")}
              activeKey={sortKey}
              direction={direction}
              onSort={onSort}
            />
          </Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell align="right">
            <SortHeader
              columnKey="tokens_out"
              label={t("tokensOut")}
              activeKey={sortKey}
              direction={direction}
              onSort={onSort}
            />
          </Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell align="right">
            <SortHeader
              columnKey="cost_usd"
              label={t("costUsd")}
              activeKey={sortKey}
              direction={direction}
              onSort={onSort}
            />
          </Table.ColumnHeaderCell>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {sorted.map((row) => (
          <Table.Row key={row.user_id}>
            <Table.Cell>
              <Text weight="medium">
                {row.display_name ?? row.user_id.split(":")[1] ?? row.user_id}
              </Text>
              <br />
              <Code size="1" color="gray" variant="ghost">
                {row.user_id}
              </Code>
            </Table.Cell>
            <Table.Cell align="right">{number.format(row.tokens_in)}</Table.Cell>
            <Table.Cell align="right">{number.format(row.tokens_out)}</Table.Cell>
            <Table.Cell align="right">
              <Text weight="medium">{currency.format(row.cost_usd)}</Text>
            </Table.Cell>
          </Table.Row>
        ))}
      </Table.Body>
    </Table.Root>
  );
}
