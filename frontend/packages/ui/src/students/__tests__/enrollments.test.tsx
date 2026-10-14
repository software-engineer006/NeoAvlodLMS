import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { apiClient } from "../../api/client";
import { ApiError } from "../../api/errors";
import { StudentGroupsPanel } from "../StudentGroupsPanel";
import { TeacherStudentProfileModal } from "../../teacher/TeacherStudentDetailDrawer";
import type { StudentDetailItem } from "../types";

const first = { id: "g1", name: "English namuna", status: "active" as const, subject_name: "English", teacher_name: "Namuna Ustoz", monthly_price: null };
const second = { id: "g2", name: "Python namuna", status: "active" as const, subject_name: "Python", teacher_name: "Boshqa Ustoz", monthly_price: null };
const pupil: StudentDetailItem = {
  id: "p", first_name: "Namuna", last_name: "O‘quvchi", phone: null, age: null, parent: null,
  parent_id: null, status: "active", group_id: first.id, group: first, telegram_connected: false,
  created_at: "2026-10-14T00:00:00Z", enrollments: [first, second].map((group) => ({ group, is_active: true, level: null, mygov_status: null, notes: null })),
};
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("read-only membership cards show all courses without requesting write selectors", () => {
  const get = vi.spyOn(apiClient, "get");
  render(<StudentGroupsPanel student={pupil} canEdit={false} onUpdated={vi.fn()} />);
  expect(screen.getByText(first.name)).toBeDefined(); expect(screen.getByText(second.name)).toBeDefined();
  expect(screen.queryByRole("button", { name: "Guruhdan olish" })).toBeNull();
  expect(screen.queryByLabelText("Qo‘shimcha guruh")).toBeNull(); expect(get).not.toHaveBeenCalled();
});

it("adds an additional course and confirms removal without changing other memberships", async () => {
  vi.spyOn(apiClient, "get").mockResolvedValue({ items: [
    { id: "g3", name: "Namuna uchinchi", max_students: 20, current_students: 5 },
    { id: "full", name: "To‘lgan", max_students: 5, current_students: 5 },
  ] });
  const put = vi.spyOn(apiClient, "put").mockResolvedValue(pupil); const updated = vi.fn();
  render(<StudentGroupsPanel student={pupil} canEdit onUpdated={updated} />);
  await screen.findByRole("option", { name: "Namuna uchinchi (5/20)" });
  expect((screen.getByRole("option", { name: "To‘lgan (5/5)" }) as HTMLOptionElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Qo‘shimcha guruh"), { target: { value: "g3" } });
  fireEvent.click(screen.getByRole("button", { name: "Guruhga biriktirish" }));
  await waitFor(() => expect(put).toHaveBeenCalledWith("/api/v1/admin/students/p/groups/g3", { is_active: true }));
  await waitFor(() => expect(updated).toHaveBeenCalledWith(pupil));
  fireEvent.click(screen.getAllByRole("button", { name: "Guruhdan olish" })[1]);
  expect(put).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Biriktirishni olish" }));
  await waitFor(() => expect(put).toHaveBeenLastCalledWith("/api/v1/admin/students/p/groups/g2", { is_active: false }));
});

it("server capacity errors preserve all displayed courses and revocation removes controls", async () => {
  vi.spyOn(apiClient, "get").mockResolvedValue({ items: [{ id: "g3", name: "Namuna uchinchi", max_students: 20, current_students: 5 }] });
  vi.spyOn(apiClient, "put").mockRejectedValue(new ApiError(409, "Guruhda bo‘sh joy yo‘q"));
  const onUpdated = vi.fn(); const { rerender } = render(<StudentGroupsPanel student={pupil} canEdit onUpdated={onUpdated} />);
  await screen.findByRole("option", { name: "Namuna uchinchi (5/20)" });
  fireEvent.change(screen.getByLabelText("Qo‘shimcha guruh"), { target: { value: "g3" } });
  fireEvent.click(screen.getByRole("button", { name: "Guruhga biriktirish" }));
  await screen.findByText("Guruhda bo‘sh joy yo‘q"); expect(onUpdated).not.toHaveBeenCalled();
  expect(screen.getByText(second.name)).toBeDefined();
  rerender(<StudentGroupsPanel student={pupil} canEdit={false} onUpdated={onUpdated} />);
  expect(screen.queryByRole("button", { name: "Guruhga biriktirish" })).toBeNull();
});

it("teacher profile request follows the selected own course when pupil identity is unchanged", async () => {
  const get = vi.spyOn(apiClient, "get").mockResolvedValueOnce({ ...pupil, group_id: "g1", group_name: "English namuna" })
    .mockResolvedValueOnce({ ...pupil, group_id: "g2", group_name: "Python namuna" });
  const selected = { ...pupil, group_id: "g1", group_name: "English namuna" };
  const { rerender } = render(<TeacherStudentProfileModal isOpen onClose={vi.fn()} student={selected} />);
  await waitFor(() => expect(get).toHaveBeenCalledWith(expect.stringContaining("group_id=g1")));
  rerender(<TeacherStudentProfileModal isOpen onClose={vi.fn()} student={{ ...selected, group_id: "g2", group_name: "Python namuna" }} />);
  await waitFor(() => expect(get).toHaveBeenCalledWith(expect.stringContaining("group_id=g2")));
});
