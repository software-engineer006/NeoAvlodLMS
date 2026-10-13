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
  ATTENDANCE_WRITE: "attendance:write",
  MESSAGES_SEND: "messages:send",
} as const;

export type PermissionKey = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

/**
 * Checks whether the current user has the specified permission.
 * - Superadmin has all permissions.
 * - Teacher has NO admin permissions.
 * - Admin has only permissions explicitly present in user.permissions.
 */
export function hasPermission(user: CurrentUser | null, permission: string): boolean {
  if (!user || user.status !== "active" || !Object.values(PERMISSIONS).includes(permission as PermissionKey)) {
    return false;
  }
  if (user.role === "superadmin") {
    return true;
  }
  if (user.role === "teacher") {
    return false;
  }
  const dependencies: Record<string, string[]> = {
    [PERMISSIONS.GROUPS_READ]: [PERMISSIONS.GROUPS_CREATE, PERMISSIONS.GROUPS_EDIT],
    [PERMISSIONS.STUDENTS_READ]: [PERMISSIONS.STUDENTS_CREATE, PERMISSIONS.STUDENTS_EDIT],
    [PERMISSIONS.ATTENDANCE_READ]: [PERMISSIONS.ATTENDANCE_WRITE],
  };
  return user.permissions.includes(permission) || (dependencies[permission] ?? []).some((write) => user.permissions.includes(write));
}

/**
 * Bot settings are strictly superadmin-only.
 */
export function canManageBot(user: CurrentUser | null): boolean {
  return Boolean(user && user.status === "active" && user.role === "superadmin");
}
