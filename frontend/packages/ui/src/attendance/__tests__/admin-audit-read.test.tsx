import { expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AdminChangesHistoryView } from "../AdminChangesHistoryView";
import { apiClient } from "../../api/client";

it("reads immutable audit and clears the previous lesson when the date changes", async () => {
  const get = vi.spyOn(apiClient, "get").mockResolvedValue({ total: 1, items: [{ id: "change", student_name: "Namuna O‘quvchi", actor_name: "Namuna Ustoz", actor_role: "teacher",
    action: "correct", old_status: "absent", new_status: "present", old_note: null, new_note: "Tekshirildi", reason: "Jurnal tekshirildi", changed_at: "2026-10-12T09:00:00Z" }] });
  const post = vi.spyOn(apiClient, "post");
  render(<AdminChangesHistoryView groups={[{ id: "g1", name: "English A" }]} />);
  fireEvent.change(screen.getByLabelText("Audit dars sanasi"), { target: { value: "2026-10-12" } });
  fireEvent.click(screen.getByRole("button", { name: "O‘zgarishlar tarixi" }));
  await screen.findByText("Jurnal tekshirildi");
  expect(get).toHaveBeenCalledWith("/api/v1/admin/attendance/groups/g1/attendance/changes?date=2026-10-12", { params: { page: 1, page_size: 20 } });
  fireEvent.change(screen.getByLabelText("Audit dars sanasi"), { target: { value: "2026-10-13" } });
  expect(screen.queryByText("Jurnal tekshirildi")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "O‘zgarishlar tarixi" }));
  await waitFor(() => expect(get).toHaveBeenLastCalledWith("/api/v1/admin/attendance/groups/g1/attendance/changes?date=2026-10-13", { params: { page: 1, page_size: 20 } }));
  expect(post).not.toHaveBeenCalled();
});
