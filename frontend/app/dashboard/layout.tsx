import type { ReactNode } from "react";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { DashboardShell } from "../../components/layout/DashboardShell";
import { ROLE_SELECTION_ROUTE } from "../../lib/constants";
import { getRoleFromSessionClaims } from "../../lib/rbac";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  const { userId, redirectToSignIn, sessionClaims } = await auth();

  if (!userId) {
    return redirectToSignIn();
  }

  const role = getRoleFromSessionClaims(
    sessionClaims as Record<string, unknown> | undefined
  );
  const resolvedRole = role;

  if (resolvedRole !== "doctor") {
    redirect(ROLE_SELECTION_ROUTE);
  }

  return (
    <DashboardShell role={resolvedRole}>
      {children}
    </DashboardShell>
  );
}
