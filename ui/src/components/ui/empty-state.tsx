import { Box, Flex, Heading, Text } from "@radix-ui/themes";
import { cn } from "@/lib/utils";

/**
 * Friendly empty-state block used when a list query returns zero rows.
 *
 * Always give users a next action — either a primary CTA button or a
 * link — otherwise empty pages feel broken rather than pristine.
 */
export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <Flex
      direction="column"
      align="center"
      justify="center"
      gap="3"
      className={cn("py-12 text-center", className)}
    >
      {icon && (
        <Box className="rounded-full bg-[var(--accent-a3)] p-4 text-[var(--accent-11)]">
          {icon}
        </Box>
      )}
      <Heading size="4">{title}</Heading>
      {description && (
        <Text color="gray" size="2" className="max-w-sm">
          {description}
        </Text>
      )}
      {action && <Box mt="2">{action}</Box>}
    </Flex>
  );
}
