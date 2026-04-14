import { AppShell } from "@/components/layout/app-shell";

/**
 * All authenticated pages share the AppShell (sidebar + header).
 * The login page is outside this layout group.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
