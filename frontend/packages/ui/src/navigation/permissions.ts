import type { CurrentUser } from "../api/types";

export const PERMISSIONS = {
  STAFF_MANAGE: "staff:manage",
  SUBJECTS_MANAGE: "subjects:manage",
  GROUPS_READ: "groups:read",
  GROUPS_CREATE: "groups:create",
  GROUPS_EDIT: "groups:edit",
  STUDENTS_READ: "students:read",
  STUDENTS_CREATE: "students:create",
  STUDENTS_EDIT: "students:edit",
  ATTENDANCE_READ: "attendance:read",
} as const;

export type PermissionKey = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

/**
 * Checks whether the current user has the specified permission.
 * - Superadmin has all permissions.
 * - Teacher has NO admin permissions.
 * - Admin has only permissions explicitly present in user.permissions.
 */
export function hasPermission(user: CurrentUser | null, permission: string): boolean {
  if (!user || user.status !== "active") {
    return false;
  }
  if (user.role === "superadmin") {
    return true;
  }
  if (user.role === "teacher") {
    return false;
  }
  return user.permissions.includes(permission) || user.permissions.includes("*");
}

/**
 * Bot settings are strictly superadmin-only.
 */
export function canManageBot(user: CurrentUser | null): boolean {
  return Boolean(user && user.status === "active" && user.role === "superadmin");
}
