export type PortalType = "admin" | "teacher";

export type RoleType = "superadmin" | "admin" | "teacher";

export type StaffStatus = "active" | "inactive";

export interface CurrentUser {
  id: string;
  username: string;
  first_name: string;
  last_name: string | null;
  phone: string | null;
  role: RoleType;
  status: StaffStatus;
  permissions: string[];
  telegram_id?: number | null;
  must_change_password?: boolean;
  avatar_url?: string | null;
}

export interface ApiValidationError {
  loc?: (string | number)[];
  msg: string;
  type?: string;
}

export interface ApiErrorPayload {
  detail?: string | ApiValidationError[];
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  params?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
}

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardStaffBreakdown {
  teachers: number;
  admins: number;
  superadmins: number;
}

export interface DashboardStats {
  groups_count: number | null;
  students_count: number | null;
  staff_count: number | null;
  staff_breakdown: DashboardStaffBreakdown | null;
}
