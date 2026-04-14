"use client";

import { Button, Flex } from "@radix-ui/themes";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CaretSortIcon,
} from "@radix-ui/react-icons";
import { useTranslations } from "next-intl";

/**
 * Sortable column header.
 *
 * Controlled — the parent owns `{ key, direction }` and the header just
 * dispatches the next intent:
 *
 *   - Click an inactive column  → sort desc by that key.
 *   - Click the active column   → flip direction (desc ↔ asc).
 *
 * A caret icon is always visible so the column is clearly marked as
 * sortable; it swaps to an arrow when the column becomes active.
 */
export type SortDirection = "asc" | "desc";

export interface SortHeaderProps<TKey extends string> {
  columnKey: TKey;
  label: string;
  activeKey: TKey | null;
  direction: SortDirection;
  onSort: (key: TKey, direction: SortDirection) => void;
}

export function SortHeader<TKey extends string>({
  columnKey,
  label,
  activeKey,
  direction,
  onSort,
}: SortHeaderProps<TKey>) {
  const t = useTranslations("cost");
  const isActive = activeKey === columnKey;

  function handleClick() {
    if (!isActive) {
      onSort(columnKey, "desc");
      return;
    }
    onSort(columnKey, direction === "desc" ? "asc" : "desc");
  }

  const icon = !isActive ? (
    <CaretSortIcon />
  ) : direction === "desc" ? (
    <ArrowDownIcon />
  ) : (
    <ArrowUpIcon />
  );

  const ariaLabel = isActive
    ? direction === "desc"
      ? t("sortDescending")
      : t("sortAscending")
    : t("sortDescending");

  return (
    <Button
      variant="ghost"
      size="1"
      color="gray"
      onClick={handleClick}
      aria-label={ariaLabel}
      aria-sort={
        isActive ? (direction === "desc" ? "descending" : "ascending") : "none"
      }
    >
      <Flex align="center" gap="1">
        {label}
        {icon}
      </Flex>
    </Button>
  );
}
