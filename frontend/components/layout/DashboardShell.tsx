import type { ReactNode } from "react";

import type { AppRole } from "@/lib/constants";

import { AppSidebar } from "./Sidebar";

type DashboardShellProps = {
  children: ReactNode;
  role: AppRole;
};

export function DashboardShell({ children, role }: DashboardShellProps) {
  return (
    <div className="flex flex-col md:flex-row h-screen overflow-hidden bg-[var(--color-off-white)] dark:bg-[var(--color-charcoal)]">
      <AppSidebar role={role} />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
