export type PortalType = "admin" | "teacher";

export type RoleType = "superadmin" | "admin" | "teacher";

export type StaffStatus = "active" | "inactive";

export interface CurrentUser {
  id: string;
  username: string;
  first_name: string;
  last_name: string;
  phone: string;
  role: RoleType;
  status: StaffStatus;
  permissions: string[];
  telegram_id?: number | null;
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
