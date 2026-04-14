import { cn } from "@/lib/utils";

/**
 * Rectangular shimmering placeholder used while data is loading.
 *
 * Keep loading skeletons *shaped like the final content* — matching
 * heights and widths eliminates Cumulative Layout Shift (CLS) when
 * the real data resolves.
 */
export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className={cn(
        "animate-pulse rounded-md bg-[var(--gray-a4)]",
        className,
      )}
      {...props}
    />
  );
}
