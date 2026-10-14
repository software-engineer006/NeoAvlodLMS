import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RoomsManagementView } from "../RoomsManagementView";
import { GroupModal } from "../GroupModal";
import { apiClient } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { CurrentUser } from "../../api/types";
import type { GroupItem } from "../types";
const user: CurrentUser = { id: "a", username: "namuna", first_name: "Namuna", last_name: null, phone: null, role: "admin", status: "active", permissions: ["rooms:manage"] };
const room = { id: "room217", name: "217", description: "Kompyuter xonasi", is_active: true, created_at: "2026-10-14T10:00:00Z", updated_at: "2026-10-14T10:00:00Z" };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("hides room controls and makes no catalogue requests without the explicit grant", () => {
  const get = vi.spyOn(apiClient, "get");
  render(<RoomsManagementView currentUser={{ ...user, permissions: ["groups:edit"] }} />);
  expect(screen.queryByRole("button", { name: "Xona qo‘shish" })).toBeNull(); expect(get).not.toHaveBeenCalled();
});

it("creates a room, handles deletion conflict and revokes controls immediately", async () => {
  vi.spyOn(apiClient, "get").mockResolvedValue([room]);
  const post = vi.spyOn(apiClient, "post").mockResolvedValue(room);
  const del = vi.spyOn(apiClient, "delete").mockRejectedValue(new ApiError(409, "Guruh biriktirilgan xonani o‘chirib bo‘lmaydi"));
  const { rerender } = render(<RoomsManagementView currentUser={user} />);
  await screen.findByText("217"); expect(screen.getByText(/14.10.2026 15:00:00/)).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Xona qo‘shish" }));
  fireEvent.change(screen.getByLabelText(/Xona nomi \/ raqami/), { target: { value: " 218 " } });
  fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/api/v1/admin/rooms", { name: "218", description: null }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  fireEvent.click(screen.getByRole("button", { name: "217 xonani o‘chirish" })); expect(del).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "O‘chirishni tasdiqlash" }));
  await screen.findByText("Guruh biriktirilgan xonani o‘chirib bo‘lmaydi");
  rerender(<RoomsManagementView currentUser={{ ...user, permissions: [] }} />);
  expect(screen.queryByRole("dialog")).toBeNull(); expect(screen.queryByText("217")).toBeNull();
});

it("group edit sends room ID and can clear the assignment using the same selector", async () => {
  const group: GroupItem = { id: "g", name: "Namuna guruh", subject_id: "s", teacher_id: "t", monthly_price: null,
    max_students: 20, current_students: 1, status: "active", days_of_week: [1,3,5], start_time: "09:00:00", end_time: "10:30:00", room_number: "217", room_id: room.id,
    subject: { id: "s", name: "Namuna fan", is_active: true }, teacher: { id: "t", first_name: "Namuna", last_name: "Ustoz", status: "active", phone: null },
    created_at: room.created_at, updated_at: room.updated_at };
  vi.spyOn(apiClient, "get").mockResolvedValue({ subjects: [group.subject], teachers: [group.teacher], rooms: [room, { ...room, id: "room218", name: "218" }] });
  const patch = vi.spyOn(apiClient, "patch").mockResolvedValue(group);
  render(<GroupModal isOpen group={group} onClose={vi.fn()} onSuccess={vi.fn()} />);
  await screen.findByRole("option", { name: "218" });
  fireEvent.change(screen.getByLabelText("Xona"), { target: { value: "room218" } });
  fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith("/api/v1/admin/groups/g", expect.objectContaining({ room_id: "room218" })));
  await waitFor(() => expect((screen.getByRole("button", { name: "Saqlash" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText("Xona"), { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));
  await waitFor(() => expect(patch).toHaveBeenLastCalledWith("/api/v1/admin/groups/g", expect.objectContaining({ room_id: null, room_number: null })));
});
