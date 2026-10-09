import type { RoleType, StaffStatus } from "../api/types";

export interface TelegramLinkState {
  deep_link?: string | null;
  expires_at?: string | null;
  expired?: boolean;
  is_expired?: boolean;
  connected?: boolean;
}

export interface StaffItem {
  id: string;
  first_name: string;
  last_name: string | null;
  username: string;
  phone: string | null;
  role: RoleType;
  status: StaffStatus;
  permissions: string[];
  telegram_connected: boolean;
  must_change_password?: boolean;
  created_at: string;
}

export interface StaffDetailItem extends StaffItem {
  telegram_link?: TelegramLinkState | null;
  telegram_link_error?: string | null;
}

export interface StaffListResponse {
  items: StaffItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface StaffCreateInput {
  first_name: string;
  last_name: string | null;
  phone: string | null;
  username: string;
  password?: string;
  role: RoleType;
  permissions: string[];
}

export interface StaffUpdateInput {
  first_name?: string;
  last_name?: string;
  phone?: string;
  permissions?: string[];
}
