import type { RoleType, StaffStatus } from "../api/types";

export interface TelegramLinkState {
  deep_link: string;
  expires_at: string;
  is_expired: boolean;
}

export interface StaffItem {
  id: string;
  first_name: string;
  last_name: string;
  username: string;
  phone: string;
  role: RoleType;
  status: StaffStatus;
  permissions: string[];
  telegram_connected: boolean;
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
  last_name: string;
  phone: string;
  username: string;
  password: string;
  role: RoleType;
  permissions: string[];
}

export interface StaffUpdateInput {
  first_name?: string;
  last_name?: string;
  phone?: string;
  permissions?: string[];
}
