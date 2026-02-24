import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import {
  DASHBOARD_ROUTES,
  DEFAULT_ROLE,
  type AppRole,
} from "./lib/constants";
import {
  dashboardPathForRole,
  getRoleFromSessionClaims,
  isAppRole,
} from "./lib/rbac";

function resolveRedirectRole(role: AppRole | null): AppRole {
  if (isAppRole(role)) {
    return role;
  }
  return DEFAULT_ROLE;
}

export default clerkMiddleware(async (auth, req) => {
  const pathname = req.nextUrl.pathname;
  const isDashboardRoute = pathname.startsWith("/dashboard");

  if (!isDashboardRoute) {
    return NextResponse.next();
  }

  const authObject = await auth();

  if (!authObject.userId) {
    return authObject.redirectToSignIn();
  }

  const role = getRoleFromSessionClaims(
    authObject.sessionClaims as Record<string, unknown> | undefined
  );

  const redirectedRole = resolveRedirectRole(role);
  const redirectedPath = dashboardPathForRole(redirectedRole);

  if (
    pathname.startsWith(DASHBOARD_ROUTES.doctor) &&
    redirectedRole !== "doctor"
  ) {
    return NextResponse.redirect(new URL(redirectedPath, req.url));
  }

  if (
    pathname.startsWith(DASHBOARD_ROUTES.patient) &&
    redirectedRole !== "patient"
  ) {
    return NextResponse.redirect(new URL(redirectedPath, req.url));
  }

  return NextResponse.next();
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
