import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TeacherAttendanceView } from "../TeacherAttendanceView";
import { AuthProvider, useAuth } from "../../auth/AuthContext";
import type { TeacherAttendanceSheet } from "../types";

const sheet: TeacherAttendanceSheet = {
  group_id: "group1", date: "2026-10-13", finalized: false, finalized_at: null,
  can_edit: true, edit_deadline: "2030-10-15T23:59:59+05:00", edit_disabled_reason: null,
  items: [{ student_id: "s1", student_first_name: "Ali", student_last_name: "Valiyev", status: null, note: null, marked_at: null }],
};
const unauthorized = () => Response.json({ detail: "Sessiya muddati tugagan" }, { status: 401 });
beforeEach(() => { vi.restoreAllMocks(); document.cookie = "neoavlod_csrf=valid-csrf; Path=/"; });
afterEach(() => { vi.unstubAllGlobals(); document.cookie = "neoavlod_csrf=; Max-Age=0; Path=/"; });

describe("Attendance survives an expired access cookie", () => {
  it("silently renews and saves the teacher's selected statuses and notes", async () => {
    let valid = false;
    const savedBodies: string[] = [];
    const fetchMock = vi.fn(async (path: string, options?: RequestInit) => {
      if (path.endsWith("/me")) return unauthorized();
      if (path.endsWith("/refresh")) { valid = true; return new Response(null, { status: 204 }); }
      if (path.endsWith("/draft")) {
        savedBodies.push(options?.body as string);
        if (!valid) return unauthorized();
        const body = JSON.parse(options?.body as string);
        return Response.json({ ...sheet, items: [{ ...sheet.items[0], ...body.items[0] }] });
      }
      return Response.json(sheet);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<TeacherAttendanceView groups={[{ id: "group1", name: "Python" }]} initialDate="2026-10-13" />);
    await screen.findByText("Ali Valiyev");
    fireEvent.click(screen.getByRole("button", { name: "Kelmadi" }));
    fireEvent.change(screen.getByPlaceholderText(/Izoh yozish/), { target: { value: "Kasal" } });
    fireEvent.click(screen.getByRole("button", { name: "Qoralama saqlash" }));
    await screen.findByText("Davomat qoralamasi muvaffaqiyatli saqlandi.");
    expect(savedBodies).toHaveLength(2);
    expect(savedBodies[1]).toBe(savedBodies[0]);
    expect(JSON.parse(savedBodies[1]).items).toEqual([{ student_id: "s1", status: "absent", note: "Kasal" }]);
    expect((screen.getByPlaceholderText(/Izoh yozish/) as HTMLInputElement).value).toBe("Kasal");
    expect(screen.queryByText("Sessiya muddati tugagan")).toBeNull();
    expect(screen.queryByText("Saqlanmagan o‘zgarishlar bor")).toBeNull();
  });

  it("retains unsaved attendance if the seven-day refresh session has ended", async () => {
    vi.stubGlobal("fetch", vi.fn(async (path: string) => path.includes("attendance?") ? Response.json(sheet) : unauthorized()));
    render(<TeacherAttendanceView groups={[{ id: "group1", name: "Python" }]} initialDate="2026-10-13" />);
    await screen.findByText("Ali Valiyev");
    fireEvent.click(screen.getByRole("button", { name: "Keldi" }));
    fireEvent.change(screen.getByPlaceholderText(/Izoh yozish/), { target: { value: "Izoh saqlansin" } });
    fireEvent.click(screen.getByRole("button", { name: "Qoralama saqlash" }));
    await screen.findByText("Sessiya muddati tugagan");
    expect((screen.getByPlaceholderText(/Izoh yozish/) as HTMLInputElement).value).toBe("Izoh saqlansin");
    expect(screen.getByText("Saqlanmagan o‘zgarishlar bor")).toBeDefined();
  });

  it("restores the teacher profile when the portal is reopened", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(new Response(null, { status: 204 })).mockResolvedValueOnce(Response.json({
        id: "teacher1", username: "teacher", role: "teacher", status: "active", permissions: [],
      }));
    vi.stubGlobal("fetch", fetchMock);
    function Profile() {
      const { user, isLoading } = useAuth();
      return <p>{isLoading ? "Yuklanmoqda" : user ? user.username : "Login qiling"}</p>;
    }
    render(<AuthProvider portal="teacher"><Profile /></AuthProvider>);
    await screen.findByText("teacher");
    expect(screen.queryByText("Login qiling")).toBeNull();
  });
});
