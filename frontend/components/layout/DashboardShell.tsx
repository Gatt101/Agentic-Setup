import type { ReactNode } from "react";

import type { AppRole } from "@/lib/constants";

import { AppSidebar } from "./Sidebar";

type DashboardShellProps = {
  children: ReactNode;
  role: AppRole;
  userId: string;
};

export function DashboardShell({ children, role, userId }: DashboardShellProps) {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50 text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100 md:flex-row">
      <AppSidebar role={role} userId={userId} />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
