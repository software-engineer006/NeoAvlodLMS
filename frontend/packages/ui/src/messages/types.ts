import { formatDateTime } from "../lib/dates";
export type RecipientKind = "parent" | "student";
export type AudienceKind = "parents" | "students" | "both";
export type AudienceScope = "selected" | "groups" | "all";
export type DeliveryStatus =
  "pending" | "delivered" | "failed" | "skipped" | "cancelled";
export type DeliveryCounts = Record<DeliveryStatus, number>;

export interface MessageGroup {
  id: string;
  name: string;
  students: number;
}
export interface MessageAudience {
  scope: AudienceScope;
  kind: AudienceKind;
  group_ids: string[];
  parent_ids: string[];
  student_ids: string[];
}
export interface RecipientOption {
  id: string;
  kind: RecipientKind;
  name: string;
  group_names: string[];
  student_names: string[];
  connected: boolean;
  connection_reason: string | null;
}
export interface RecipientPage {
  items: RecipientOption[];
  total: number;
  page: number;
  page_size: number;
}
export interface MessageDraft {
  title: string;
  body: string;
  audience: MessageAudience;
}
export interface MessagePreview {
  digest: string;
  message: string;
  bot_configured: boolean;
  total: number;
  eligible: number;
  unlinked: number;
  duplicates: number;
  parents: number;
  students: number;
  sample: RecipientOption[];
}
export interface MessageCampaign {
  id: string;
  title: string;
  body: string;
  author_name: string;
  created_at: string;
  cancelled_at: string | null;
  audience: MessageAudience;
  status: "queued" | "completed" | "partial" | "cancelled";
  counts: DeliveryCounts;
  total: number;
}
export interface DeliveryItem {
  id: string;
  kind: RecipientKind;
  name: string;
  group_names: string[];
  status: DeliveryStatus;
  attempts: number;
  last_error: string | null;
  delivered_at: string | null;
  available_at: string;
  retried_at: string | null;
}
export interface MessageDetail {
  campaign: MessageCampaign;
  recipients: DeliveryItem[];
  total: number;
  page: number;
  page_size: number;
}
export interface MessageHistoryPage {
  items: MessageCampaign[];
  total: number;
  page: number;
  page_size: number;
  summary: DeliveryCounts;
}
export const MESSAGE_API = "/api/v1/admin/messages";
export const emptyCounts: DeliveryCounts = {
  pending: 0,
  delivered: 0,
  failed: 0,
  skipped: 0,
  cancelled: 0,
};
export const kindLabels: Record<AudienceKind, string> = {
  parents: "Ota-onalar",
  students: "O‘quvchilar",
  both: "Ota-onalar va o‘quvchilar",
};
export const scopeLabels: Record<AudienceScope, string> = {
  selected: "Tanlanganlar",
  groups: "Guruhlar bo‘yicha",
  all: "Barchaga",
};
export const deliveryLabels: Record<DeliveryStatus, string> = {
  pending: "Navbatda",
  delivered: "Yetkazildi",
  failed: "Xato",
  skipped: "Yuborilmadi",
  cancelled: "Bekor qilindi",
};
export const formatMessage = (title: string, body: string) =>
  `NeoAvlod LMS\n\n${title.trim()}\n\n${body.trim()}`;
export function createRequestId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
export const messageError = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Xabarlar xizmatida xatolik yuz berdi";
export const messageTime = formatDateTime;
