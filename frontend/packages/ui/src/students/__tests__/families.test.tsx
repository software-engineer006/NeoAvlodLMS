import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StudentModal } from "../StudentModal";
import { apiClient } from "../../api/client";
import type { StudentDetailItem } from "../types";
const parent = { id: "parent", first_name: "Namuna", last_name: "Ota-ona", phone: "+998900000000", telegram_connected: true, child_count: 2, created_at: "2026-10-14T00:00:00Z" };
const pupil: StudentDetailItem = { id: "p", first_name: "Namuna", last_name: "O‘quvchi", phone: null, age: null,
  status: "active", group_id: "g", group: { id: "g", name: "Namuna kurs", status: "active" }, parent_id: parent.id, parent,
  telegram_connected: false, created_at: parent.created_at };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("selects an existing family explicitly and never submits a cloned guardian body", async () => {
  vi.spyOn(apiClient, "get").mockResolvedValue({ items: [parent] });
  const patch = vi.spyOn(apiClient, "patch").mockResolvedValue(pupil);
  render(<StudentModal isOpen student={pupil} onClose={vi.fn()} onSuccess={vi.fn()} />);
  await screen.findByText(/Bu ota-onaga 2 ta bola bog‘langan/);
  fireEvent.change(screen.getByLabelText("Ota-onani bog‘lash"), { target: { value: "existing" } });
  await screen.findByRole("option", { name: /Namuna Ota-ona/ });
  expect(screen.queryByLabelText("Ota-ona telefon raqami")).toBeNull();
  fireEvent.change(screen.getByLabelText("Mavjud ota-ona"), { target: { value: parent.id } });
  fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith("/api/v1/admin/students/p", expect.objectContaining({ parent_id: parent.id, parent: undefined })));
});

it("explicitly detaches only this child and preserves optional blank profile fields", async () => {
  const patch = vi.spyOn(apiClient, "patch").mockResolvedValue(pupil);
  render(<StudentModal isOpen student={pupil} onClose={vi.fn()} onSuccess={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Ota-onani bog‘lash"), { target: { value: "none" } });
  expect(screen.getByLabelText(/^Ism/)).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith("/api/v1/admin/students/p", expect.objectContaining({ parent_id: null, parent: undefined })));
});
