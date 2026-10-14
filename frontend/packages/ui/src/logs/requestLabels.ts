import type { LogEvent } from "./types";

const portals: Record<string, string> = { admin: "Admin paneli", teacher: "O‘qituvchi paneli" };
const requests = /* @__PURE__ */ buildRequests();
function buildRequests(): Record<string, string> {
  const requests: Record<string, string> = {
    "GET /admin/dashboard/stats": "Dashboard ko‘rsatkichlari olindi",
    "GET /admin/attendance": "Davomat ro‘yxati olindi",
    "GET /admin/attendance/pending": "Davomat olinmagan guruhlar olindi",
    "GET /admin/attendance/groups": "Davomat uchun guruhlar olindi",
    "GET /admin/attendance/history": "Davomat tarixi olindi",
    "GET /admin/attendance/message-template": "Davomat xabari shabloni olindi",
    "POST /admin/attendance/message-template/preview": "Davomat xabari namunasi tekshirildi",
    "PUT /admin/attendance/message-template": "Davomat xabari shablonini saqlash so‘rovi",
    "GET /admin/attendance/groups/{group_id}/history": "Guruh davomat tarixi olindi",
    "GET /admin/lookups/group-options": "Guruh tanlash ro‘yxati olindi",
    "GET /admin/lookups/student-groups": "O‘quvchi guruhlari olindi",
    "GET /admin/lookups/rooms": "Xona tanlash ro‘yxati olindi",
    "GET /admin/lookups/parents": "Ota-ona tanlash ro‘yxati olindi",
    "GET /admin/logs": "Loglar ro‘yxati olindi",
    "GET /admin/logs/days": "Log mavjud kunlar olindi",
    "GET /admin/logs/{day}/download": "Kunlik log yuklash so‘rovi",
    "GET /admin/logs/{day}/{event_id}": "Log tafsilotlari olindi",
    "GET /admin/settings/bot": "Telegram bot sozlamalari olindi",
    "POST /admin/settings/bot": "Telegram bot sozlamalarini saqlash so‘rovi",
    "PUT /admin/settings/bot/username": "Telegram bot nomini yangilash so‘rovi",
    "POST /admin/settings/bot/reload-status": "Telegram bot ish holati tekshirildi",
    "GET /admin/messages": "Xabarlar tarixi olindi",
    "GET /admin/messages/groups": "Xabar yuborish guruhlari olindi",
    "GET /admin/messages/recipients": "Xabar qabul qiluvchilar ro‘yxati olindi",
    "POST /admin/messages/preview": "Xabar yuborishdan oldin tekshirildi",
    "POST /admin/messages": "Xabar yuborish so‘rovi",
    "GET /admin/messages/{campaign_id}": "Xabar yetkazilish tafsilotlari olindi",
    "POST /admin/messages/{campaign_id}/cancel": "Xabar yuborishni to‘xtatish so‘rovi",
    "POST /admin/messages/{campaign_id}/retry": "Xabarni qayta yuborish so‘rovi",
    "GET /teacher/groups": "O‘z guruhlari ro‘yxati olindi",
    "GET /teacher/groups/{group_id}": "O‘z guruhi tafsilotlari olindi",
    "GET /teacher/groups/{group_id}/students": "Guruh o‘quvchilari ro‘yxati olindi",
    "GET /teacher/students/{student_id}": "O‘quvchi tafsilotlari olindi",
    "GET /teacher/attendance/history": "O‘z guruhining davomat tarixi olindi",
    "GET /auth/me": "Joriy hisob ma’lumotlari olindi",
    "PATCH /auth/me": "Profilni tahrirlash so‘rovi",
    "POST /auth/avatar": "Profil rasmini yuklash so‘rovi",
    "DELETE /auth/avatar": "Profil rasmini o‘chirish so‘rovi",
    "POST /auth/refresh": "Sessiyani yangilash so‘rovi",
    "POST /auth/logout": "Hisobdan chiqish so‘rovi",
    "POST /auth/login": "Kirish uchun tasdiqlash so‘rovi",
    "POST /auth/login/confirm": "Kirishni tasdiqlash so‘rovi",
    "POST /auth/password/change": "Parolni o‘zgartirish so‘rovi",
    "POST /auth/password/reset": "Parolni tiklash so‘rovi",
    "POST /auth/password/reset/confirm": "Parol tiklashni tasdiqlash so‘rovi",
  };
  for (const [resource, singular, plural, id] of [
    ["staff", "Xodim", "Xodimlar", "staff_id"], ["subjects", "Fan", "Fanlar", "subject_id"],
    ["groups", "Guruh", "Guruhlar", "group_id"], ["students", "O‘quvchi", "O‘quvchilar", "student_id"],
    ["rooms", "Xona", "Xonalar", "room_id"],
  ]) {
    const base = `/admin/${resource}`, item = `${base}/{${id}}`;
    Object.assign(requests, {
      [`GET ${base}`]: `${plural} ro‘yxati olindi`, [`POST ${base}`]: `${singular} qo‘shish so‘rovi`,
      [`GET ${item}`]: `${singular} tafsilotlari olindi`, [`PATCH ${item}`]: `${singular} tahrirlash so‘rovi`,
      [`DELETE ${item}`]: `${singular} o‘chirish so‘rovi`,
      [`POST ${item}/activate`]: `${singular} faollashtirish so‘rovi`,
      [`POST ${item}/deactivate`]: `${singular} faolsizlantirish so‘rovi`,
      [`POST ${item}/telegram-link`]: `${singular} uchun Telegram ulanish havolasi so‘raldi`,
    });
  }
  for (const prefix of ["/admin/attendance", "/teacher"]) {
    const base = `${prefix}/groups/{group_id}/attendance`;
    Object.assign(requests, {
      [`GET ${base}`]: "Guruhning davomat varaqasi olindi",
      [`POST ${base}/draft`]: "Davomat qoralamasini saqlash so‘rovi",
      [`POST ${base}/finalize`]: "Davomatni yakunlash so‘rovi",
      [`POST ${base}/correct`]: "Davomatni tuzatish so‘rovi",
      [`GET ${base}/changes`]: "Davomat o‘zgarishlari auditini olish so‘rovi",
    });
  }
  requests["GET /admin/groups/{group_id}/attendance/history"] = "Guruh davomat tarixi olindi";
  requests["POST /admin/students/{student_id}/transfer"] = "O‘quvchini boshqa guruhga ko‘chirish so‘rovi";
  requests["PUT /admin/students/{student_id}/groups/{group_id}"] = "O‘quvchining guruhga biriktirishini saqlash so‘rovi";
  requests["PATCH /admin/students/{student_id}/groups/{group_id}"] = "O‘quvchining kurs ma’lumotlarini tahrirlash so‘rovi";
  requests["POST /admin/students/{student_id}/parent/telegram-link"] = "Ota-ona Telegram ulanish havolasi so‘raldi";
  requests["GET /teacher/groups/{group_id}/attendance/history"] = "Guruh davomat tarixi olindi";
  return requests;
}

export function logPortalLabel(event: LogEvent): string {
  const value = event.details.portal;
  if (typeof value === "string" && portals[value]) return portals[value];
  if (event.actor) return portals[event.actor.role === "teacher" ? "teacher" : "admin"];
  const route = event.details.route;
  return typeof route === "string" ? portals[route.split("/")[3]] || "" : "";
}
export function logRequestLabel(event: LogEvent): string {
  const method = typeof event.details.method === "string" ? event.details.method : "";
  const route = typeof event.details.route === "string" ? event.details.route.replace(/^\/api\/v1/, "")
    .replace(/^\/auth\/(?:\{portal\}|admin|teacher)\//, "/auth/") : "";
  const source = logPortalLabel(event), target = portals[route.split("/")[1]];
  const panel = source && target && source !== target ? `${source} → ${target}` : source || target;
  const rejected = event.details.outcome === "rejected" || (typeof event.details.status === "number" && event.details.status >= 400);
  const label = requests[`${method} ${route}`] || `Aniqlanmagan bo‘limdagi ${method || "API"} so‘rovi`;
  return `${panel ? `${panel} — ` : ""}${rejected ? label.replace(/ olindi$/, " so‘raldi") : label}${rejected ? " (rad etildi)" : ""}`;
}
