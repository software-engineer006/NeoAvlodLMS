import { expect, it } from "vitest";
import { logDate, logEventLabel, logExactUTC, logTime } from "./format";
import type { LogEvent } from "./types";
const event: LogEvent = { id: "1", at: "2026-10-14T10:37:47.123456Z", day: "2026-10-14",
  actor: { id: "sample", name: "Namuna", username: "sample", role: "superadmin" },
  action: "http.request", entity: { type: null, id: null, name: null }, changes: {}, private_changed: [],
  details: { method: "GET", route: "/api/v1/admin/dashboard/stats", status: 200, outcome: "success" },
  source: "http", request_id: "sample" };
it("formats fixed Tashkent dates, midnight rollover and exact UTC without ISO display", () => {
  expect(logTime(event.at)).toBe("14.10.2026 15:37:47");
  expect(logTime("2026-10-13T19:00:00Z")).toBe("14.10.2026 00:00:00");
  expect(logExactUTC(event.at)).toBe("14.10.2026 10:37:47.123456");
  expect(logDate("2026-10-14")).toBe("14.10.2026");
  expect(logTime("invalid")).toBe("—");
});
it.each([
  ["GET", "/admin/dashboard/stats", "Dashboard ko‘rsatkichlari olindi"],
  ["GET", "/admin/students", "O‘quvchilar ro‘yxati olindi"],
  ["PATCH", "/admin/students/{student_id}", "O‘quvchi tahrirlash so‘rovi"],
  ["POST", "/admin/attendance/groups/{group_id}/attendance/correct", "Davomatni tuzatish so‘rovi"],
  ["GET", "/admin/logs", "Loglar ro‘yxati olindi"],
])("identifies admin %s %s without inventing a page click", (method, route, label) => {
  expect(logEventLabel({ ...event, details: { method, route: `/api/v1${route}` } })).toBe(`Admin paneli — ${label}`);
});
it("identifies teacher self/group reads and rejected cross-portal attempts", () => {
  const teacher = { ...event, actor: { ...event.actor!, role: "teacher" as const },
    details: { portal: "teacher", method: "GET", route: "/api/v1/auth/{portal}/me" } };
  expect(logEventLabel(teacher)).toBe("O‘qituvchi paneli — Joriy hisob ma’lumotlari olindi");
  expect(logEventLabel({ ...teacher, details: { ...teacher.details, route: "/api/v1/admin/logs", outcome: "rejected" } }))
    .toBe("O‘qituvchi paneli → Admin paneli — Loglar ro‘yxati so‘raldi (rad etildi)");
});
it("supports old request records and labels actual login by portal", () => {
  expect(logEventLabel(event)).toBe("Admin paneli — Dashboard ko‘rsatkichlari olindi");
  expect(logEventLabel({ ...event, action: "auth.login", details: { portal: "teacher" } }))
    .toBe("O‘qituvchi paneli — Tizimga kirish");
  expect(logEventLabel({ ...event, details: { method: "POST", route: "/api/v1/unmapped" } }))
    .toContain("Aniqlanmagan bo‘limdagi POST so‘rovi");
});
