export type AttendanceStatusType = "present" | "absent" | "late";

export interface AdminAttendanceItem {
  attendance_id: string;
  date: string;
  group_id: string;
  group_name: string;
  teacher_id: string;
  teacher_name: string;
  student_id: string;
  student_name: string;
  status: AttendanceStatusType;
  note: string | null;
  marked_at: string;
  finalized: boolean;
  batch_id: string | null;
}

export interface AdminAttendanceListResponse {
  items: AdminAttendanceItem[];
  total: number;
  page: number;
  page_size: number;
}

export function formatAttendanceStatus(status: AttendanceStatusType): {
  label: string;
  variant: "success" | "danger" | "warning";
} {
  switch (status) {
    case "present":
      return { label: "Bor", variant: "success" };
    case "absent":
      return { label: "Yo‘q", variant: "danger" };
    case "late":
      return { label: "Kechikdi", variant: "warning" };
    default:
      return { label: status, variant: "warning" };
  }
}

export interface MonthlyAttendanceRecord {
  attendance_id: string;
  student_id: string;
  student_name: string;
  date: string;
  status: AttendanceStatusType;
  note: string | null;
}

export interface StudentMonthlyAttendanceSummary {
  student_id: string;
  student_name: string;
  present_count: number;
  late_count: number;
  absent_count: number;
  attended_count: number;
  total_lessons: number;
}

export interface GroupMonthlyAttendanceSummary {
  total_lessons: number;
  total_records: number;
  present_count: number;
  late_count: number;
  absent_count: number;
}

export interface GroupMonthlyAttendanceHistoryResponse {
  group_id: string;
  group_name: string;
  month: string;
  dates: string[];
  records: MonthlyAttendanceRecord[];
  students_summary: StudentMonthlyAttendanceSummary[];
  summary: GroupMonthlyAttendanceSummary;
}
