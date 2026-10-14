import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LogsView } from "./LogsView";
import type { LogEvent, LogPage } from "./types";
import type { CurrentUser } from "../api/types";
import { apiClient } from "../api/client";
import { PERMISSIONS } from "../navigation/permissions";

const user: CurrentUser = { id: "namuna-super", username: "namuna_admin", first_name: "Namuna",
  last_name: "Admin", phone: null, role: "superadmin", status: "active", permissions: [] };
const entry: LogEvent = { id: "12", at: "2026-10-14T07:00:01.123456Z", day: "2026-10-14",
  actor: { id: "namuna-teacher", name: "Namuna Ustoz", username: "namuna_ustoz", role: "teacher" },
  action: "attendance.correct", entity: { type: "attendance", id: "namuna-record", name: "Namuna O‘quvchi" },
  changes: { status: { before: "absent", after: "present" }, note: { before: null, after: "Aniqlashtirildi" } },
  private_changed: [], details: { reason: "Jurnal tekshirildi", group: { id: "namuna-group", name: "Namuna guruh" } },
  source: "http", request_id: "synthetic-request" };
const page: LogPage = { items: [entry], actors: [entry.actor!], actions: [entry.action],
  total: 1, next_cursor: null, page_size: 50 };

beforeEach(() => { vi.restoreAllMocks(); vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-14T07:00:00Z")); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
function mockPage(data: LogPage = page) {
  return vi.spyOn(apiClient, "get").mockImplementation((url) => Promise.resolve(url.endsWith("/days") ? [] : data));
}

it.each(["admin", "teacher", "inactive"])("denies %s with full grants and never fetches logs", (role) => {
  const get = mockPage();
  render(<LogsView currentUser={{ ...user, role: role === "teacher" ? "teacher" : "admin",
    status: role === "inactive" ? "inactive" : "active", permissions: Object.values(PERMISSIONS) }} />);
  expect(screen.getByText("Ruxsat berilmagan")).toBeDefined();
  expect(get).not.toHaveBeenCalled();
});

it("shows actor, exact seconds and immutable old/new/reason details safely", async () => {
  mockPage();
  render(<LogsView currentUser={user} />);
  await screen.findAllByText("Namuna Ustoz");
  expect(screen.getByText(/12:00:01/)).toBeDefined();
  expect(screen.getByText("14.10.2026 12:00:01")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: /Davomat tuzatildi tafsilotlari/ }));
  await screen.findByRole("dialog");
  expect(screen.getByText("Jurnal tekshirildi")).toBeDefined();
  expect(screen.getByText("Kelmadi")).toBeDefined();
  expect(screen.getByText("Keldi")).toBeDefined();
  expect(screen.getByText(/14\.10\.2026 07:00:01\.123456/)).toBeDefined();
  expect(screen.queryByRole("button", { name: /O‘chirish|Tahrirlash/ })).toBeNull();
});

it("shows exact portal and resource for old HTTP logs in both row and details", async () => {
  const http = { ...entry, action: "http.request", actor: { ...entry.actor!, role: "superadmin" as const },
    details: { method: "GET", route: "/api/v1/admin/dashboard/stats", status: 200, outcome: "success" } };
  mockPage({ ...page, items: [http], actions: [http.action] });
  render(<LogsView currentUser={user} />);
  await screen.findByText("Admin paneli — Dashboard ko‘rsatkichlari olindi");
  expect(screen.queryByText("Paneldagi so‘rov")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Dashboard ko‘rsatkichlari olindi tafsilotlari/ }));
  expect(screen.getByRole("dialog")).toBeDefined();
  expect(screen.getByText("Admin paneli")).toBeDefined();
});

it("applies server filters and resets the cursor when the day changes", async () => {
  const get = mockPage({ ...page, total: 51, next_cursor: "2026-10-14T07:00:01.123456Z|12" });
  render(<LogsView currentUser={user} />);
  await screen.findAllByText("Namuna Ustoz");
  fireEvent.click(screen.getByRole("button", { name: "Keyingi" }));
  await waitFor(() => expect(get).toHaveBeenCalledWith("/api/v1/admin/logs", expect.objectContaining({
    params: expect.objectContaining({ cursor: "2026-10-14T07:00:01.123456Z|12" }) })));
  fireEvent.change(screen.getByLabelText("Log kuni"), { target: { value: "2026-10-13" } });
  await waitFor(() => expect(get).toHaveBeenLastCalledWith("/api/v1/admin/logs", expect.objectContaining({
    params: expect.objectContaining({ day: "2026-10-13", cursor: undefined }) })));
  await screen.findAllByText("Namuna Ustoz");
  fireEvent.change(screen.getByLabelText("Xodim"), { target: { value: "namuna-teacher" } });
  await waitFor(() => expect(get).toHaveBeenLastCalledWith("/api/v1/admin/logs", expect.objectContaining({
    params: expect.objectContaining({ actor_id: "namuna-teacher" }) })));
});

it("removes details immediately on role revocation and cancels pending loads", async () => {
  mockPage();
  const { rerender } = render(<LogsView currentUser={user} />);
  await screen.findAllByText("Namuna Ustoz");
  fireEvent.click(screen.getByRole("button", { name: /tafsilotlari/ }));
  expect(screen.getByRole("dialog")).toBeDefined();
  rerender(<LogsView currentUser={{ ...user, role: "admin", permissions: Object.values(PERMISSIONS) }} />);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.queryByText("Namuna Ustoz")).toBeNull();
});

it("handles loading errors, retry and an empty day", async () => {
  const get = vi.spyOn(apiClient, "get").mockImplementation((url) => url.endsWith("/days") ? Promise.resolve([]) : Promise.reject(new Error("Arxiv tekshiruvi xatosi")));
  render(<LogsView currentUser={user} />);
  await screen.findByText("Arxiv tekshiruvi xatosi");
  get.mockImplementation((url) => Promise.resolve(url.endsWith("/days") ? [] : { ...page, items: [], total: 0 }));
  fireEvent.click(screen.getByRole("button", { name: "Qayta urinish" }));
  await screen.findByText("Log yozuvi topilmadi");
});

it("aborts a pending page after role revocation and rejects its late result", async () => {
  let resolvePage!: (value: LogPage) => void;
  const pending = new Promise<LogPage>((resolve) => { resolvePage = resolve; });
  const get = vi.spyOn(apiClient, "get").mockImplementation((url) => url.endsWith("/days") ? Promise.resolve([]) : pending);
  const { rerender } = render(<LogsView currentUser={user} />);
  await waitFor(() => expect(get).toHaveBeenCalled());
  const call = get.mock.calls.find(([url]) => url === "/api/v1/admin/logs");
  const signal = call?.[1]?.signal;
  rerender(<LogsView currentUser={{ ...user, role: "admin" }} />);
  expect(signal?.aborted).toBe(true);
  await act(async () => resolvePage(page));
  expect(screen.queryByText("Namuna Ustoz")).toBeNull();
});

it("renders untrusted notes as text without executing markup", async () => {
  const markup = "<img src=x onerror=alert('fixture')>";
  mockPage({ ...page, items: [{ ...entry, changes: { note: { before: null, after: markup } } }] });
  render(<LogsView currentUser={user} />);
  await screen.findAllByText("Namuna Ustoz");
  fireEvent.click(screen.getByRole("button", { name: /tafsilotlari/ }));
  expect(screen.getByText(markup)).toBeDefined();
  expect(document.querySelector("img[onerror]")).toBeNull();
});

it("requests a CSRF-protected compressed download without storing it in browser storage", async () => {
  const get = vi.spyOn(apiClient, "get").mockImplementation((url) => Promise.resolve(
    url.endsWith("/days") ? [] : url.endsWith("/download") ? new Blob(["fixture"], { type: "application/gzip" }) : page));
  const create = vi.fn(() => "blob:synthetic-log");
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: create });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<LogsView currentUser={user} />);
  await screen.findAllByText("Namuna Ustoz");
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Kunlik logni yuklash" })); });
  expect(get).toHaveBeenCalledWith("/api/v1/admin/logs/2026-10-14/download", expect.objectContaining({ responseType: "blob" }));
  expect(create).toHaveBeenCalledTimes(1); expect(click).toHaveBeenCalledTimes(1);
  expect(localStorage.getItem("neoavlod_logs")).toBeNull();
  expect(sessionStorage.getItem("neoavlod_logs")).toBeNull();
});
