import type { ReactNode } from "react";
import { auth } from "@clerk/nextjs/server";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { DashboardShell } from "../../components/layout/DashboardShell";
import { ROLE_COOKIE_NAME, ROLE_SELECTION_ROUTE } from "../../lib/constants";
import { getRoleFromSessionClaims, parseRole } from "../../lib/rbac";

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
  const cookieStore = await cookies();
  const cookieRole = parseRole(cookieStore.get(ROLE_COOKIE_NAME)?.value);
  const resolvedRole = role ?? cookieRole;

  if (!resolvedRole) {
    redirect(ROLE_SELECTION_ROUTE);
  }

  return (
    <DashboardShell role={resolvedRole} userId={userId}>
      {children}
    </DashboardShell>
  );
}
