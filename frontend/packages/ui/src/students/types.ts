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
  subject_id?: string | null;
  subject_name?: string | null;
  teacher_id?: string | null;
  teacher_name?: string | null;
  days_of_week?: number[] | null;
  start_time?: string | null;
  end_time?: string | null;
  room_number?: string | null;
  monthly_price?: number | string | null;
}

export interface StudentAttendanceStats {
  month: string;
  present_count: number;
  late_count: number;
  absent_count: number;
  attended_count: number;
  total_lessons: number;
}

export interface StudentItem {
  id: string;
  first_name: string;
  last_name: string | null;
  phone: string | null;
  age: number | null;
  school_grade?: string | null;
  import_notes?: string[];
  status: "active" | "inactive";
  group_id: string;
  parent_id: string | null;
  telegram_connected: boolean;
  created_at: string;
  parent: ParentItem | null;
  group: GroupSummaryItem;
}

export interface StudentDetailItem extends StudentItem {
  parent: ParentDetailItem | null;
  telegram_link?: TelegramLinkState | null;
  telegram_link_error?: string | null;
  attendance_stats?: StudentAttendanceStats | null;
}

export interface StudentListResponse {
  items: StudentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface StudentCreateInput {
  first_name: string;
  last_name: string | null;
  phone: string | null;
  age: number | null;
  group_id: string;
  parent: ParentCreateInput | null;
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
