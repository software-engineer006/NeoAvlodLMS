import type { StudentAttendanceStats } from "../students/types";

export interface TeacherSubjectSummary {
  id: string;
  name: string;
}

export interface TeacherGroupItem {
  id: string;
  name: string;
  subject_id: string;
  subject: TeacherSubjectSummary;
  monthly_price: number | string | null;
  max_students: number;
  current_students: number;
  status: "active" | "inactive" | "archived";
  days_of_week: number[];
  start_time: string | null;
  end_time: string | null;
  room_number: string | null;
  created_at: string;
}

export interface TeacherParentItem {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  telegram_connected: boolean;
}

export interface TeacherStudentItem {
  id: string;
  first_name: string;
  last_name: string | null;
  phone: string | null;
  age: number | null;
  school_grade?: string | null;
  import_notes?: string[];
  status: "active" | "inactive" | "archived";
  group_id: string;
  group_name: string;
  telegram_connected: boolean;
  parent: TeacherParentItem | null;
  created_at: string;
  subject_name?: string | null;
  teacher_name?: string | null;
  days_of_week?: number[] | null;
  start_time?: string | null;
  end_time?: string | null;
  room_number?: string | null;
  monthly_price?: number | string | null;
  attendance_stats?: StudentAttendanceStats | null;
}

export type TeacherAttendanceStatus = "present" | "absent" | "late";

export interface TeacherAttendanceEntry {
  student_id: string;
  student_first_name: string;
  student_last_name: string | null;
  status: TeacherAttendanceStatus | null;
  note: string | null;
  marked_at: string | null;
}

export interface TeacherAttendanceSheet {
  group_id: string;
  date: string;
  finalized: boolean;
  finalized_at: string | null;
  items: TeacherAttendanceEntry[];
}

export interface TeacherDraftItemIn {
  student_id: string;
  status: TeacherAttendanceStatus;
  note?: string | null;
}

export interface TeacherDraftSaveIn {
  date: string;
  items: TeacherDraftItemIn[];
}

export interface TeacherFinalizeIn {
  date: string;
  items?: TeacherDraftItemIn[] | null;
}
