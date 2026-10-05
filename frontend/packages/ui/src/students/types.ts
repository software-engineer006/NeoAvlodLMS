import type { TelegramLinkState } from "../staff/types";

export interface ParentItem {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  telegram_connected: boolean;
  created_at: string;
}

export interface ParentDetailItem extends ParentItem {
  telegram_link?: TelegramLinkState | null;
  telegram_link_error?: string | null;
}

export interface ParentCreateInput {
  first_name: string;
  last_name: string;
  phone: string;
}

export interface ParentUpdateInput {
  first_name?: string;
  last_name?: string;
  phone?: string;
}

export interface GroupSummaryItem {
  id: string;
  name: string;
  status: "active" | "inactive";
}

export interface StudentItem {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  age: number;
  status: "active" | "inactive";
  group_id: string;
  parent_id: string;
  telegram_connected: boolean;
  created_at: string;
  parent: ParentItem;
  group: GroupSummaryItem;
}

export interface StudentDetailItem extends StudentItem {
  parent: ParentDetailItem;
  telegram_link?: TelegramLinkState | null;
  telegram_link_error?: string | null;
}

export interface StudentListResponse {
  items: StudentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface StudentCreateInput {
  first_name: string;
  last_name: string;
  phone: string;
  age: number;
  group_id: string;
  parent: ParentCreateInput;
}

export interface StudentUpdateInput {
  first_name?: string;
  last_name?: string;
  phone?: string;
  age?: number;
  parent?: ParentUpdateInput;
}

export interface StudentTransferInput {
  target_group_id: string;
}
