import { beforeEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { apiClient } from "../../api/client";
import { TeacherStudentProfileModal } from "../../teacher/TeacherStudentDetailDrawer";
import { StudentProfileModal } from "../StudentDetailDrawer";
import type { CurrentUser } from "../../api/types";

const partial = {
  id: "partial", first_name: "Original Full Name", last_name: null, age: null, phone: null,
  school_grade: "7-sinf", import_notes: ["Original source note"], parent: null,
  parent_id: null, group_id: "g", group_name: "Python", status: "active" as const,
  telegram_connected: false, created_at: "2026-10-01T00:00:00Z",
  monthly_price: null, group: { id: "g", name: "Python", status: "active" as const, monthly_price: null },
};
const admin: CurrentUser = { id: "a", username: "admin", first_name: "User", last_name: null,
  phone: null, role: "superadmin", status: "active", permissions: [] };
beforeEach(() => vi.restoreAllMocks());
it("shows partial admin profile without fabricated age, parent or zero price", async () => {
  vi.spyOn(apiClient, "get").mockResolvedValue(partial);
  const { container } = render(<StudentProfileModal isOpen onClose={() => {}} studentId="partial" currentUser={admin} />);
  await screen.findAllByText("Original Full Name");
  expect(screen.getAllByText("7-sinf").length).toBeGreaterThan(0);
  expect(screen.getByText("Original source note")).toBeDefined();
  expect(screen.queryByText("0 so‘m")).toBeNull();
  expect(container.querySelector('a[href^="tel:"]')).toBeNull();
  expect(screen.queryByRole("button", { name: /Yangi ota-ona havolasini/ })).toBeNull();
});
it("shows partial teacher profile and never produces a missing-contact link", async () => {
  vi.spyOn(apiClient, "get").mockResolvedValue(partial);
  const { container } = render(<TeacherStudentProfileModal isOpen onClose={() => {}} student={partial} />);
  await screen.findByText("Original Full Name");
  expect(screen.getByText("Original source note")).toBeDefined();
  expect(screen.queryByText("0 so‘m")).toBeNull();
  expect(container.querySelector('a[href^="tel:"]')).toBeNull();
});
