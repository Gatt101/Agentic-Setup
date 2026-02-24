import { DEFAULT_ROLE, type AppRole } from "./constants";

export type UserRole = AppRole;

export function getDefaultRole(): UserRole {
  return DEFAULT_ROLE;
}
