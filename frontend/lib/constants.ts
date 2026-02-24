export const APP_ROLES = ["doctor", "patient"] as const;

export type AppRole = (typeof APP_ROLES)[number];

export const DEFAULT_ROLE: AppRole = "patient";

export const ROLE_SELECTION_ROUTE = "/select-role";

export const ROLE_COOKIE_NAME = "orthoassist-role";

export const DASHBOARD_ROUTES: Record<AppRole, string> = {
  doctor: "/dashboard/doctor",
  patient: "/dashboard/patient",
};

export const AUTH_ROUTES = {
  signIn: "/sign-in",
  signUp: "/sign-up",
} as const;
