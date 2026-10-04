import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import {
  DASHBOARD_ROUTES,
  ROLE_SELECTION_ROUTE,
} from "./lib/constants";
import {
  getRoleFromSessionClaims,
} from "./lib/rbac";

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

  const resolvedRole = getRoleFromSessionClaims(
    authObject.sessionClaims as Record<string, unknown> | undefined
  );

  if (resolvedRole !== "doctor") {
    return redirectToRoleSelection(req);
  }

  if (pathname === "/dashboard" || pathname.startsWith(DASHBOARD_ROUTES.patient)) {
    return NextResponse.redirect(new URL(DASHBOARD_ROUTES.doctor, req.url));
  }

  return NextResponse.next();
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
