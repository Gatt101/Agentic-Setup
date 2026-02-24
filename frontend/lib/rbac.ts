import {
  APP_ROLES,
  DASHBOARD_ROUTES,
  DEFAULT_ROLE,
  type AppRole,
} from "./constants";

type SessionClaimsLike = Record<string, unknown> | null | undefined;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isAppRole(value: unknown): value is AppRole {
  return APP_ROLES.includes(value as AppRole);
}

function extractRoleFromRecord(record: Record<string, unknown>): AppRole | null {
  const directRole = record.role;
  if (isAppRole(directRole)) {
    return directRole;
  }

  const metadataKeys = [
    "metadata",
    "publicMetadata",
    "public_metadata",
    "unsafeMetadata",
    "unsafe_metadata",
  ] as const;

  for (const key of metadataKeys) {
    const metadata = record[key];
    if (!isRecord(metadata)) {
      continue;
    }

    if (isAppRole(metadata.role)) {
      return metadata.role;
    }

    const nestedKeys = ["public", "unsafe"] as const;
    for (const nestedKey of nestedKeys) {
      const nestedMetadata = metadata[nestedKey];
      if (!isRecord(nestedMetadata)) {
        continue;
      }

      if (isAppRole(nestedMetadata.role)) {
        return nestedMetadata.role;
      }
    }
  }

  return null;
}

export function hasRole(role: AppRole, allowed: AppRole[]): boolean {
  return allowed.includes(role);
}

export function getRoleFromSessionClaims(
  claims: SessionClaimsLike
): AppRole | null {
  if (!isRecord(claims)) {
    return null;
  }

  return extractRoleFromRecord(claims);
}

export function parseRole(value: unknown): AppRole | null {
  return isAppRole(value) ? value : null;
}

export function resolveRoleOrDefault(claims: SessionClaimsLike): AppRole {
  return getRoleFromSessionClaims(claims) ?? DEFAULT_ROLE;
}

export function dashboardPathForRole(role: AppRole): string {
  return DASHBOARD_ROUTES[role];
}
