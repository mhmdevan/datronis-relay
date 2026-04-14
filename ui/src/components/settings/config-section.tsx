"use client";

import { Box, Card, Flex, Heading, Separator, Text } from "@radix-ui/themes";

/**
 * Reusable section wrapper used by `config-form.tsx`.
 *
 * Every config section (Claude, Scheduler, Metrics, Attachments, Logging)
 * has the same layout: title + description + separator + fields. Pulling
 * that into a single component keeps the form file itself readable and
 * means visual tweaks (spacing, divider colour) happen in one place.
 *
 * Purely presentational — no form state, no i18n calls. The parent hands
 * in the already-translated strings and the field slot.
 */
export interface ConfigSectionProps {
  title: string;
  description: string;
  children: React.ReactNode;
}

export function ConfigSection({
  title,
  description,
  children,
}: ConfigSectionProps) {
  return (
    <Card>
      <Flex direction="column" gap="1" mb="3">
        <Heading size="4">{title}</Heading>
        <Text size="2" color="gray">
          {description}
        </Text>
      </Flex>
      <Separator size="4" mb="4" />
      <Box>{children}</Box>
    </Card>
  );
}
