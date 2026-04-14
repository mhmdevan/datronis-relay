"use client";

import { Button, Callout, Flex } from "@radix-ui/themes";
import { ExclamationTriangleIcon } from "@radix-ui/react-icons";
import { useTranslations } from "next-intl";

/**
 * Inline error block with a retry button.
 *
 * Used by every page's error branch — the "retry" prop hooks into
 * `useApi().retry` so a click reruns the failed request without
 * reloading the whole page.
 */
export interface ErrorStateProps {
  title: string;
  description?: string;
  onRetry?: () => void;
}

export function ErrorState({ title, description, onRetry }: ErrorStateProps) {
  const t = useTranslations("common");

  return (
    <Callout.Root color="red" role="alert">
      <Callout.Icon>
        <ExclamationTriangleIcon />
      </Callout.Icon>
      <Flex direction="column" gap="2" className="w-full">
        <Callout.Text weight="medium">{title}</Callout.Text>
        {description && <Callout.Text size="1">{description}</Callout.Text>}
        {onRetry && (
          <Flex mt="1">
            <Button size="1" variant="soft" color="red" onClick={onRetry}>
              {t("tryAgain")}
            </Button>
          </Flex>
        )}
      </Flex>
    </Callout.Root>
  );
}
