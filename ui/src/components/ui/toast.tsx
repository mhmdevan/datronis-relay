"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import {
  CheckCircledIcon,
  CrossCircledIcon,
  InfoCircledIcon,
} from "@radix-ui/react-icons";
import { cn } from "@/lib/utils";

/**
 * Toast provider + `useToast()` hook.
 *
 * Radix `@radix-ui/react-toast` gives us the accessibility primitives
 * (swipe dismiss, aria-live region, pause-on-hover); we layer a tiny
 * queue on top so mutation handlers can call `toast.success("...")`
 * imperatively without threading props around.
 */

export type ToastVariant = "success" | "error" | "info";

interface ToastItem {
  id: number;
  variant: ToastVariant;
  title: string;
  description?: string;
}

interface ToastContextValue {
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be called inside <ToastProvider>");
  }
  return ctx;
}

let toastCounter = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const push = useCallback(
    (variant: ToastVariant, title: string, description?: string) => {
      toastCounter += 1;
      const id = toastCounter;
      setToasts((prev) => [...prev, { id, variant, title, description }]);
    },
    [],
  );

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({
      success: (title, description) => push("success", title, description),
      error: (title, description) => push("error", title, description),
      info: (title, description) => push("info", title, description),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      <ToastPrimitive.Provider swipeDirection="right" duration={4000}>
        {children}
        {toasts.map((t) => (
          <ToastPrimitive.Root
            key={t.id}
            onOpenChange={(open) => !open && remove(t.id)}
            className={cn(
              "rt-BaseCard rt-r-size-2 rt-variant-surface",
              "flex items-start gap-3 p-3",
              "rounded-[var(--radius-3)] border",
              "data-[state=open]:animate-in data-[state=open]:slide-in-from-right-full",
              "data-[state=closed]:animate-out data-[state=closed]:fade-out",
              "bg-[var(--color-panel-solid)] shadow-[var(--shadow-4)]",
              variantBorder(t.variant),
            )}
          >
            <span
              className={cn("mt-[2px] flex-shrink-0", variantColor(t.variant))}
              aria-hidden
            >
              {variantIcon(t.variant)}
            </span>
            <div className="min-w-0 flex-1">
              <ToastPrimitive.Title className="text-sm font-medium">
                {t.title}
              </ToastPrimitive.Title>
              {t.description && (
                <ToastPrimitive.Description className="mt-0.5 text-xs text-[var(--gray-11)]">
                  {t.description}
                </ToastPrimitive.Description>
              )}
            </div>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport
          className={cn(
            "fixed end-4 bottom-4 z-50",
            "flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2",
            "outline-none",
          )}
        />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

function variantIcon(variant: ToastVariant): React.ReactNode {
  if (variant === "success") return <CheckCircledIcon width={18} height={18} />;
  if (variant === "error") return <CrossCircledIcon width={18} height={18} />;
  return <InfoCircledIcon width={18} height={18} />;
}

function variantColor(variant: ToastVariant): string {
  if (variant === "success") return "text-[var(--green-11)]";
  if (variant === "error") return "text-[var(--red-11)]";
  return "text-[var(--blue-11)]";
}

function variantBorder(variant: ToastVariant): string {
  if (variant === "success") return "border-[var(--green-a6)]";
  if (variant === "error") return "border-[var(--red-a6)]";
  return "border-[var(--blue-a6)]";
}
