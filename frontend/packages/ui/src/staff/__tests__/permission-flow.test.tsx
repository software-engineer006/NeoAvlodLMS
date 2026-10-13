import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StaffModal } from "../StaffModal";
import { apiClient } from "../../api/client";
import { PERMISSIONS } from "../../navigation/permissions";
import type { CurrentUser } from "../../api/types";
import { createRequestId } from "../../messages/types";

const boss: CurrentUser = { id: "boss", username: "boss", first_name: "Namuna", last_name: null,
  phone: null, status: "active", role: "superadmin", permissions: [] };
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function open() {
  render(<StaffModal isOpen staff={null} currentUser={boss} onClose={() => undefined} onSuccess={() => undefined} />);
  fireEvent.change(screen.getByLabelText("Xodim roli"), { target: { value: "admin" } });
}
it("write selects dependent read, removing read removes writes and full grant sends the exact catalogue", async () => {
  const post = vi.spyOn(apiClient, "post").mockResolvedValue({ ...boss, role: "admin" }); open();
  fireEvent.click(screen.getByLabelText("Guruh yaratish"));
  expect((screen.getByLabelText("Guruhlarni ko‘rish") as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getByLabelText("Guruhlarni ko‘rish"));
  expect((screen.getByLabelText("Guruh yaratish") as HTMLInputElement).checked).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Barcha ruxsatlarni berish" }));
  expect(screen.getAllByRole("checkbox").every((node) => (node as HTMLInputElement).checked)).toBe(true);
  fireEvent.change(screen.getByLabelText(/^Ism/), { target: { value: "Namuna" } });
  fireEvent.change(screen.getByLabelText(/Foydalanuvchi nomi/), { target: { value: "new_admin" } });
  fireEvent.change(screen.getByLabelText("Telefon raqami"), { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "Yaratish" }));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/api/v1/admin/staff", expect.objectContaining({ role: "admin", permissions: Object.values(PERMISSIONS) })));
});
it("does not expose grant controls to staff-managing administrators", () => {
  render(<StaffModal isOpen staff={null} currentUser={{ ...boss, role: "admin", permissions: ["staff:manage"] }} onClose={() => undefined} onSuccess={() => undefined} />);
  expect(screen.queryByRole("button", { name: "Barcha ruxsatlarni berish" })).toBeNull();
  expect(screen.queryByLabelText("Xodim roli")).toBeNull();
});
it("creates a secure UUID when randomUUID is unavailable in HTTP development contexts", () => {
  const random = vi.fn((bytes: Uint8Array) => { bytes.fill(0xab); return bytes; });
  vi.stubGlobal("crypto", { getRandomValues: random });
  expect(createRequestId()).toMatch(/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/);
  expect(random).toHaveBeenCalledTimes(1);
});
