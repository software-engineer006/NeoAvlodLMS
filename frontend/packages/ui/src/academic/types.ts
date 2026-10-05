export interface SubjectItem {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  active_groups: number;
  total_groups: number;
  created_at: string;
}

export interface SubjectListResponse {
  items: SubjectItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface SubjectCreateInput {
  name: string;
  description?: string | null;
}

export interface SubjectUpdateInput {
  name?: string;
  description?: string | null;
}

export interface TeacherSummary {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  status: "active" | "inactive";
}

export interface SubjectSummary {
  id: string;
  name: string;
  is_active: boolean;
}

export interface GroupItem {
  id: string;
  name: string;
  subject_id: string;
  teacher_id: string;
  monthly_price: number | string;
  max_students: number;
  current_students: number;
  status: "active" | "inactive";
  days_of_week: number[];
  start_time: string;
  end_time: string;
  room_number: string;
  created_at: string;
  updated_at: string;
  subject: SubjectSummary;
  teacher: TeacherSummary;
}

export interface GroupListResponse {
  items: GroupItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface GroupCreateInput {
  name: string;
  subject_id: string;
  teacher_id: string;
  monthly_price: number;
  max_students: number;
  days_of_week: number[];
  start_time: string;
  end_time: string;
  room_number: string;
}

export interface GroupUpdateInput {
  name?: string;
  subject_id?: string;
  teacher_id?: string;
  monthly_price?: number;
  max_students?: number;
  days_of_week?: number[];
  start_time?: string;
  end_time?: string;
  room_number?: string;
}

export const DAYS_OF_WEEK = [
  { value: 1, label: "Dushanba", short: "Dush" },
  { value: 2, label: "Seshanba", short: "Sesh" },
  { value: 3, label: "Chorshanba", short: "Chor" },
  { value: 4, label: "Payshanba", short: "Pay" },
  { value: 5, label: "Juma", short: "Jum" },
  { value: 6, label: "Shanba", short: "Shan" },
  { value: 7, label: "Yakshanba", short: "Yak" },
];

export function formatDaysOfWeek(days: number[]): string {
  if (!days || days.length === 0) return "-";
  const sorted = [...days].sort((a, b) => a - b);
  const jsonKey = sorted.join(",");
  if (jsonKey === "1,3,5") return "Dush / Chor / Juma";
  if (jsonKey === "2,4,6") return "Sesh / Pay / Shan";
  if (jsonKey === "1,2,3,4,5,6") return "Dush-Shan (Har kuni)";

  return sorted
    .map((d) => DAYS_OF_WEEK.find((day) => day.value === d)?.short || `${d}`)
    .join(", ");
}

export function formatPrice(price: number | string): string {
  const num = typeof price === "string" ? parseFloat(price) : price;
  if (isNaN(num)) return "0 so‘m";
  return new Intl.NumberFormat("uz-UZ").format(num) + " so‘m";
}
