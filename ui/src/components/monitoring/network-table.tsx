"use client";

import { Badge, Card, Table, Text } from "@radix-ui/themes";
import { useTranslations } from "next-intl";
import type { NetworkInterface } from "@/lib/schemas";

interface NetworkTableProps {
  interfaces: NetworkInterface[];
}

export function NetworkTable({ interfaces }: NetworkTableProps) {
  const t = useTranslations("monitoring.network");

  return (
    <Card>
      <Text size="3" weight="bold" mb="3" asChild>
        <div>{t("title")}</div>
      </Text>
      <Table.Root variant="surface" size="1">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>{t("interface")}</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>{t("status")}</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>{t("ipv4")}</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell className="hidden md:table-cell">
              {t("ipv6")}
            </Table.ColumnHeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {interfaces.map((iface) => (
            <Table.Row key={iface.name}>
              <Table.Cell>
                <Text size="2" weight="medium">
                  <code>{iface.name}</code>
                </Text>
              </Table.Cell>
              <Table.Cell>
                <Badge
                  color={
                    iface.status === "up"
                      ? "green"
                      : iface.status === "down"
                        ? "red"
                        : "gray"
                  }
                >
                  {t(iface.status)}
                </Badge>
              </Table.Cell>
              <Table.Cell>
                <Text size="1">{iface.ipv4 ?? "—"}</Text>
              </Table.Cell>
              <Table.Cell className="hidden md:table-cell">
                <Text size="1" className="max-w-[200px] truncate block">
                  {iface.ipv6 ?? "—"}
                </Text>
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
    </Card>
  );
}
