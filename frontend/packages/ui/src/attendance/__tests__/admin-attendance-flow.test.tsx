import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AdminAttendanceView } from "../AdminAttendanceView";
import { apiClient } from "../../api/client";
import type { CurrentUser } from "../../api/types";
import type { TeacherAttendanceSheet } from "../../teacher/types";

const user: CurrentUser = {
  id: "admin", username: "admin", first_name: "Admin", last_name: null, phone: null,
  role: "admin", status: "active", permissions: ["attendance:read", "attendance:write"],
};
const groups = [
  { id: "group1", name: "Python 1", teacher_id: "t1", teacher_name: "Birinchi o‘qituvchi" },
  { id: "group2", name: "Python 2", teacher_id: "t2", teacher_name: "Ikkinchi o‘qituvchi" },
];
const sheet: TeacherAttendanceSheet = {
  group_id: "group1", date: "2026-10-05", finalized: true, finalized_at: "2026-10-05T10:00:00Z",
  can_edit: true, edit_deadline: null, edit_disabled_reason: null,
  items: [{ student_id: "s1", student_first_name: "Ali", student_last_name: "Valiyev",
    status: "present", note: "Oldingi izoh", marked_at: "2026-10-05T10:00:00Z" }],
};

describe("Shared administrator attendance", () => {
  beforeEach(() => { vi.restoreAllMocks(); vi.useFakeTimers({ toFake: ["Date"] }); vi.setSystemTime(new Date("2026-10-05T10:00:00Z")); });
  afterEach(() => { vi.useRealTimers(); });

  it("opens all groups, requires a reason and displays the saved change history", async () => {
    vi.spyOn(apiClient, "get").mockImplementation((url) => {
      if (url.endsWith("/groups")) return Promise.resolve(groups);
      if (url.includes("/pending")) return Promise.resolve([groups[1]]);
      if (url.includes("/changes")) return Promise.resolve({ total: 1, items: [{
        id: "change1", student_name: "Ali Valiyev", actor_name: "Admin", actor_role: "admin",
        action: "correct", old_status: "present", new_status: "absent", old_note: "Oldingi izoh",
        new_note: "Kasal", reason: "Jurnal tekshirildi", changed_at: "2026-10-05T10:10:00Z",
      }] });
      if (url.includes("/attendance?")) return Promise.resolve(sheet);
      return Promise.resolve({ items: [], total: 0 });
    });
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({
      ...sheet, items: [{ ...sheet.items[0], status: "absent", note: "Kasal" }],
    });
    render(<AdminAttendanceView currentUser={user} />);
    await screen.findByText("Ali Valiyev");
    const options = screen.getByLabelText("Guruhni tanlang") as HTMLSelectElement;
    expect(Array.from(options.options).map((option) => option.value)).toEqual(["group1", "group2"]);
    expect(screen.getByText("Davomat olinmagan darslar")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Kelmadi" }));
    fireEvent.change(screen.getByPlaceholderText(/Izoh yozish/), { target: { value: "Kasal" } });
    fireEvent.click(screen.getByRole("button", { name: "Tuzatishni saqlash" }));
    expect(post).not.toHaveBeenCalled();
    expect(screen.getByText("Administrator tuzatish sababini kiritishi shart")).toBeDefined();
    fireEvent.change(screen.getByLabelText("Tuzatish sababi"), { target: { value: "Jurnal tekshirildi" } });
    fireEvent.click(screen.getByRole("button", { name: "Tuzatishni saqlash" }));
    await screen.findByText("Davomat tuzatishlari muvaffaqiyatli saqlandi.");
    expect(post).toHaveBeenCalledWith("/api/v1/admin/attendance/groups/group1/attendance/correct", {
      date: "2026-10-05", items: [{ student_id: "s1", status: "absent", note: "Kasal" }], reason: "Jurnal tekshirildi",
    });
    fireEvent.click(screen.getByRole("button", { name: "O‘zgarishlar tarixi" }));
    await screen.findByText("Jurnal tekshirildi");
    expect(screen.getByText("Oldingi izoh")).toBeDefined();
    expect(screen.getByText("Administrator")).toBeDefined();
  });

  it("saves a new lesson and finalizes it through the admin routes", async () => {
    const draft = { ...sheet, finalized: false, finalized_at: null, items: [{ ...sheet.items[0], status: null, note: null }] };
    vi.spyOn(apiClient, "get").mockImplementation((url) => {
      if (url.endsWith("/groups")) return Promise.resolve(groups);
      if (url.includes("/pending")) return Promise.resolve([]);
      if (url.includes("/attendance?")) return Promise.resolve(draft);
      return Promise.resolve({ items: [], total: 0 });
    });
    const post = vi.spyOn(apiClient, "post").mockResolvedValueOnce({
      ...draft, items: [{ ...sheet.items[0], note: null }],
    }).mockResolvedValueOnce(sheet);
    render(<AdminAttendanceView currentUser={user} />);
    await screen.findByText("Ali Valiyev");
    fireEvent.click(screen.getByRole("button", { name: "Keldi" }));
    fireEvent.click(screen.getByRole("button", { name: "Qoralama saqlash" }));
    await screen.findByText("Davomat qoralamasi muvaffaqiyatli saqlandi.");
    expect(post.mock.calls[0][0]).toBe("/api/v1/admin/attendance/groups/group1/attendance/draft");
    fireEvent.click(screen.getByRole("button", { name: "Davomatni yakunlash" }));
    fireEvent.click(screen.getByRole("button", { name: "Tasdiqlash va yakunlash" }));
    await waitFor(() => expect(post.mock.calls[1][0]).toBe("/api/v1/admin/attendance/groups/group1/attendance/finalize"));
    await screen.findByRole("button", { name: "Tuzatishni saqlash" });
  });
});
