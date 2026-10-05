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
