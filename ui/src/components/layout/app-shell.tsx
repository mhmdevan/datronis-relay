import { Flex, Box } from "@radix-ui/themes";
import { Sidebar } from "./sidebar";
import { Header } from "./header";

/**
 * The app shell wraps every authenticated page. It provides:
 * - A fixed sidebar on desktop (hidden on mobile, replaced by MobileNav in the header)
 * - A sticky header with the page title, locale switcher, and theme toggle
 * - A scrollable main content area
 */
export function AppShell({
  children,
  title,
}: {
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <Flex className="min-h-screen">
      <Sidebar />
      <Flex direction="column" className="flex-1 min-w-0">
        <Header title={title} />
        <Box asChild p="4" className="flex-1">
          <main>{children}</main>
        </Box>
      </Flex>
    </Flex>
  );
}
