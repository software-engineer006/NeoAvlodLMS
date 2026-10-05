export interface TeacherSubjectSummary {
  id: string;
  name: string;
}

export interface TeacherGroupItem {
  id: string;
  name: string;
  subject_id: string;
  subject: TeacherSubjectSummary;
  monthly_price: number | string;
  max_students: number;
  current_students: number;
  status: "active" | "inactive" | "archived";
  days_of_week: number[];
  start_time: string;
  end_time: string;
  room_number: string;
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
  last_name: string;
  phone: string;
  age: number;
  status: "active" | "inactive" | "archived";
  group_id: string;
  group_name: string;
  telegram_connected: boolean;
  parent: TeacherParentItem;
  created_at: string;
}

export type TeacherAttendanceStatus = "present" | "absent" | "late";

export interface TeacherAttendanceEntry {
  student_id: string;
  student_first_name: string;
  student_last_name: string;
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
