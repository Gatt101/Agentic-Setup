import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import {
  DASHBOARD_ROUTES,
  ROLE_COOKIE_NAME,
  ROLE_SELECTION_ROUTE,
  type AppRole,
} from "./lib/constants";
import {
  dashboardPathForRole,
  getRoleFromSessionClaims,
  parseRole,
} from "./lib/rbac";

function resolveRole(
  claims: Record<string, unknown> | undefined,
  cookieRole: string | undefined
): AppRole | null {
  const claimsRole = getRoleFromSessionClaims(claims);
  if (claimsRole) {
    return claimsRole;
  }

  return parseRole(cookieRole);
}

function redirectToRoleSelection(req: Request): NextResponse {
  return NextResponse.redirect(new URL(ROLE_SELECTION_ROUTE, req.url));
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

  const cookieRole = req.cookies.get(ROLE_COOKIE_NAME)?.value;

  const resolvedRole = resolveRole(
    authObject.sessionClaims as Record<string, unknown> | undefined,
    cookieRole
  );

  if (!resolvedRole) {
    return redirectToRoleSelection(req);
  }

  if (pathname === "/dashboard") {
    return NextResponse.redirect(new URL(dashboardPathForRole(resolvedRole), req.url));
  }

  if (
    pathname.startsWith(DASHBOARD_ROUTES.doctor) &&
    resolvedRole !== "doctor"
  ) {
    return NextResponse.redirect(
      new URL(dashboardPathForRole(resolvedRole), req.url)
    );
  }

  if (
    pathname.startsWith(DASHBOARD_ROUTES.patient) &&
    resolvedRole !== "patient"
  ) {
    return NextResponse.redirect(
      new URL(dashboardPathForRole(resolvedRole), req.url)
    );
  }

  return NextResponse.next();
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
