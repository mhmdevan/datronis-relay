"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";

/**
 * Minimal SWR-style data fetching hook.
 *
 * Deliberately not pulling in SWR or React Query for Phase UI-1 — the
 * dashboard's needs are small (list pages + detail views with manual
 * mutations), so a ~50-line hook with AbortController + retry is enough.
 *
 * Features:
 *   - AbortController cancels in-flight requests on unmount/refetch.
 *   - `refetch()` lets callers trigger a revalidation (e.g. after a
 *     successful mutation).
 *   - `retry()` is a no-op alias for `refetch()` that documents intent
 *     when used from an error-state "Try again" button.
 *   - The `fetcher` identity is captured via a ref so callers can pass
 *     inline arrow functions without retriggering.
 */
export type UseApiState<T> = {
  data: T | undefined;
  error: ApiError | undefined;
  isLoading: boolean;
  isValidating: boolean;
  refetch: () => void;
  retry: () => void;
};

export function useApi<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
): UseApiState<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<ApiError | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [isValidating, setIsValidating] = useState(false);
  const [tick, setTick] = useState(0);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    // Only the first load should show the skeleton; subsequent refetches
    // keep the stale data visible and raise `isValidating` instead.
    if (data === undefined) {
      setIsLoading(true);
    } else {
      setIsValidating(true);
    }

    fetcherRef
      .current(controller.signal)
      .then((value) => {
        if (cancelled) return;
        setData(value);
        setError(undefined);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if ((err as Error)?.name === "AbortError") return;
        const apiErr =
          err instanceof ApiError
            ? err
            : new ApiError(0, "unknown", (err as Error).message);
        setError(apiErr);
      })
      .finally(() => {
        if (cancelled) return;
        setIsLoading(false);
        setIsValidating(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
    // `key` + `tick` drive revalidation; `data` is read for the skeleton
    // decision but is deliberately not in the dep list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  return { data, error, isLoading, isValidating, refetch, retry: refetch };
}
