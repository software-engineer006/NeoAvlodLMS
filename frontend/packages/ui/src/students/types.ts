import type { TelegramLinkState } from "../staff/types";

export interface ParentItem {
  child_count?: number | null;
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
  school_name?: string | null;
  import_notes?: string[];
  status: "active" | "inactive";
  group_id: string;
  parent_id: string | null;
  telegram_connected: boolean;
  created_at: string;
  parent: ParentItem | null;
  group: GroupSummaryItem;
  enrollments?: StudentEnrollment[];
}

export interface StudentEnrollment {
  group: GroupSummaryItem;
  is_active: boolean;
  level: string | null;
  mygov_status: string | null;
  notes: string | null;
}

export const studentEnrollments = (student: StudentItem): StudentEnrollment[] =>
  student.enrollments ?? [{ group: student.group, is_active: true, level: null, mygov_status: null, notes: null }];

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
  parent_id?: string | null;
  school_grade?: string | null;
  school_name?: string | null;
  first_name: string;
  last_name: string | null;
  phone: string | null;
  age: number | null;
  group_id: string;
  parent: ParentCreateInput | null;
}

export interface StudentUpdateInput {
  parent_id?: string | null;
  school_grade?: string | null;
  school_name?: string | null;
  first_name?: string;
  last_name?: string;
  phone?: string;
  age?: number;
  parent?: ParentUpdateInput;
}

export interface StudentTransferInput {
  target_group_id: string;
  source_group_id?: string;
  reason: string;
}
