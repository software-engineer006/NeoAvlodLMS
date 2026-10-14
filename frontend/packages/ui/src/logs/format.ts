import { formatDate, formatDateTime, formatExactDateTime } from "../lib/dates";
import type { AuditValue, LogEvent } from "./types";
import { logPortalLabel, logRequestLabel } from "./requestLabels";

const entities: Record<string, string> = {
  staff: "Xodim", subject: "Fan", group: "Guruh", student: "O‘quvchi",
  parent: "Ota-ona", attendance: "Davomat", message: "Xabar", bot: "Bot",
  message_delivery: "Xabar yetkazilishi",
  enrollment: "O‘quvchining guruhga biriktirishi",
  room: "Xona",
  attendance_template: "Davomat xabari shabloni",
  dataset: "O‘quv ma’lumotlari",
};
const verbs: Record<string, string> = {
  insert: "qo‘shildi", update: "yangilandi", delete: "o‘chirildi",
  activated: "faollashtirildi", deactivated: "faolsizlantirildi",
  group_changed: "guruhga biriktirildi", draft: "qoralamasi saqlandi",
  correct: "tuzatildi", finalize: "yakunlandi",
  transferred: "guruhlar orasida ko‘chirildi",
  refreshed: "yangilandi",
};
const actions: Record<string, string> = {
  "auth.login": "Tizimga kirish", "auth.logout": "Tizimdan chiqish",
  "auth.refresh": "Sessiya yangilandi", "auth.refresh_replay": "Takroriy token rad etildi",
  "auth.password_changed": "Parol o‘zgartirildi", "auth.password_reset": "Parol tiklandi",
  "auth.password_rejected": "Kirish paroli rad etildi", "auth.otp_rejected": "Tasdiqlash rad etildi",
  "auth.login_rejected": "Kirish rad etildi", "auth.challenge_requested": "Tasdiqlash so‘raldi",
  "auth.challenge_delivered": "Tasdiqlash kodi yetkazildi",
  "auth.challenge_delivery_failed": "Tasdiqlash yetkazilmadi",
  "http.request": "Panel amallari", "audit.download": "Kunlik log yuklab olindi",
  "telegram.account_linked": "Telegram hisobi ulandi",
};
export const logActionLabel = (action: string) => {
  if (actions[action]) return actions[action];
  const [entity, verb] = action.split(".");
  return entities[entity] && verbs[verb] ? `${entities[entity]} ${verbs[verb]}` : action;
};
export const logEntityLabel = (entity: string | null) => entity ? entities[entity] || entity : "—";
export function logEventLabel(event: LogEvent): string {
  if (event.action === "http.request") return logRequestLabel(event);
  const portal = event.source === "http" || event.action.startsWith("auth.") ? logPortalLabel(event) : "";
  return `${portal ? `${portal} — ` : ""}${logActionLabel(event.action)}`;
}
export const logTime = formatDateTime;
export const logExactTime = formatExactDateTime;
export const logDate = (value: string) => value === "—" ? value : formatDate(value);
export const logRejected = (event: LogEvent) => event.details.outcome === "rejected" ||
  /(?:rejected|failed|replay)$/.test(event.action);
export function logValue(value: AuditValue | undefined): string {
  if (value == null) return "—";
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "Ha" : "Yo‘q";
  if (!Array.isArray(value) && typeof value.name === "string") return value.name;
  return JSON.stringify(value);
}
export function logFieldValue(field: string, value: AuditValue): string {
  const labels: Record<string, string> = { present: "Keldi", absent: "Kelmadi", late: "Kech qoldi",
    active: "Faol", inactive: "Faol emas", superadmin: "Superadmin", admin: "Administrator", teacher: "O‘qituvchi" };
  if (typeof value === "string" && ["date", "lesson_date"].includes(field)) return logDate(value);
  if (typeof value === "string" && field.endsWith("_at")) return logTime(value);
  return ["status", "role"].includes(field) && typeof value === "string" ? labels[value] || value : logValue(value);
}
