import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AttendanceTemplateView } from "../AttendanceTemplateView";
import { apiClient } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { CurrentUser } from "../../api/types";
const user: CurrentUser = { id: "a", username: "namuna", first_name: "Namuna", last_name: null, phone: null, role: "admin", status: "active", permissions: ["attendance:write"] };
const data = { body: "Namuna {student_name} {date}", version: 1, placeholders: ["student_name", "date"], preview: "Namuna O‘quvchi 14.10.2026", updated_at: "2026-10-14T10:00:00Z", changed_by: "a", editor_name: "Namuna Administrator" };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("template controls never fetch for a reader or teacher", () => {
  const get = vi.spyOn(apiClient, "get");
  const { rerender } = render(<AttendanceTemplateView currentUser={{ ...user, permissions: ["attendance:read"] }} />);
  expect(get).not.toHaveBeenCalled(); expect(screen.queryByLabelText("Davomat xabari matni")).toBeNull();
  rerender(<AttendanceTemplateView currentUser={{ ...user, role: "teacher" }} />); expect(get).not.toHaveBeenCalled();
});

it("requires preview of the edited body and saves the version alongside the exact text", async () => {
  vi.spyOn(apiClient, "get").mockResolvedValue(data);
  const post = vi.spyOn(apiClient, "post").mockResolvedValue({ message: "Yangi namuna 14.10.2026" });
  const put = vi.spyOn(apiClient, "put").mockResolvedValue({ ...data, body: "Yangi {student_name} {date}", version: 2 });
  render(<AttendanceTemplateView currentUser={user} />);
  await screen.findByLabelText("Davomat xabari matni");
  expect(screen.getByText(/14.10.2026 15:00:00/)).toBeDefined();
  fireEvent.change(screen.getByLabelText("Davomat xabari matni"), { target: { value: "Yangi {student_name} {date}" } });
  expect((screen.getByRole("button", { name: "Shablonni saqlash" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Matnni ko‘rib chiqish" }));
  await screen.findByText("Yangi namuna 14.10.2026");
  expect(post).toHaveBeenCalledWith("/api/v1/admin/attendance/message-template/preview", { body: "Yangi {student_name} {date}" });
  fireEvent.click(screen.getByRole("button", { name: "Shablonni saqlash" }));
  await waitFor(() => expect(put).toHaveBeenCalledWith("/api/v1/admin/attendance/message-template", { body: "Yangi {student_name} {date}", expected_version: 1 }));
  await screen.findByText(/Versiya: 2/);
});

it("preserves the draft when another editor changed the server version", async () => {
  vi.spyOn(apiClient, "get").mockResolvedValueOnce(data).mockResolvedValueOnce({ ...data, version: 2, body: "Boshqa xodim matni" });
  vi.spyOn(apiClient, "post").mockResolvedValue({ message: "Yangi namuna" });
  vi.spyOn(apiClient, "put").mockRejectedValue(new ApiError(409, "Shablon boshqa xodim tomonidan yangilangan"));
  render(<AttendanceTemplateView currentUser={user} />);
  await screen.findByLabelText("Davomat xabari matni");
  fireEvent.change(screen.getByLabelText("Davomat xabari matni"), { target: { value: "Yangi matn" } });
  fireEvent.click(screen.getByRole("button", { name: "Matnni ko‘rib chiqish" })); await screen.findByText("Yangi namuna");
  fireEvent.click(screen.getByRole("button", { name: "Shablonni saqlash" }));
  await screen.findByText("Shablon boshqa xodim tomonidan yangilangan");
  expect((screen.getByLabelText("Davomat xabari matni") as HTMLTextAreaElement).value).toBe("Yangi matn");
  fireEvent.click(screen.getByRole("button", { name: "Saqlangan versiyani tekshirish" }));
  await screen.findByText(/Versiya: 2/);
  expect((screen.getByLabelText("Davomat xabari matni") as HTMLTextAreaElement).value).toBe("Yangi matn");
  expect((screen.getByRole("button", { name: "Shablonni saqlash" }) as HTMLButtonElement).disabled).toBe(true);
});
