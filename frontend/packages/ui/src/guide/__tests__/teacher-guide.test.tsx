import { expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { CurrentUser } from "../../api/types";
import { TeacherGuideView } from "../TeacherGuideView";
import { teacherTopics } from "../teacherTopics";
import { visibleGuideTopics } from "../types";

const teacher: CurrentUser = { id: "teacher", username: "teacher", first_name: "Namuna", last_name: null,
  phone: null, role: "teacher", status: "active", permissions: ["staff:manage", "messages:send"] };
it("offers all eleven teacher topics and no admin actions even with forged grants", () => {
  expect(visibleGuideTopics(teacher, "teacher", teacherTopics).length).toBe(11);
  render(<TeacherGuideView currentUser={teacher} />);
  const nav = screen.getByRole("navigation", { name: "Qo‘llanma mavzulari" });
  expect(within(nav).getAllByRole("button").length).toBe(11);
  expect(within(nav).queryByText(/Administrator va barcha/)).toBeNull();
  expect(within(nav).queryByText(/barchaga xabar/)).toBeNull();
  expect(teacherTopics.every((topic) => topic.id.startsWith("teacher-") && topic.imageAlt && topic.steps.length >= 3)).toBe(true);
});
it.each(["admin", "superadmin"] as const)("denies the %s role in teacher documentation", (role) => {
  render(<TeacherGuideView currentUser={{ ...teacher, role }} />);
  expect(screen.queryByLabelText("Qo‘llanmadan qidirish")).toBeNull();
});
it("searches the exact Tashkent correction boundary and navigates only to teacher attendance", () => {
  const navigate = vi.fn(); render(<TeacherGuideView currentUser={teacher} onNavigate={navigate} />);
  fireEvent.change(screen.getByLabelText("Qo‘llanmadan qidirish"), { target: { value: "chorshanba 23:59" } });
  expect(screen.getByRole("heading", { name: "Yakunlangan davomatni 2 kun ichida tuzatish" })).toBeDefined();
  expect(screen.getByText(/Dars sanasidan keyingi ikkinchi kunning/)).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Bo‘limga o‘tish" })); expect(navigate).toHaveBeenCalledWith("attendance");
  fireEvent.change(screen.getByLabelText("Qo‘llanmadan qidirish"), { target: { value: "botni sozlash" } });
  expect(screen.getByText("Mavzu topilmadi")).toBeDefined();
});
it("closes the guide if the teacher account becomes inactive", () => {
  const view = render(<TeacherGuideView currentUser={teacher} />);
  fireEvent.click(screen.getByRole("button", { name: /Rasmni kattalashtirish/ }));
  view.rerender(<TeacherGuideView currentUser={{ ...teacher, status: "inactive" }} />);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.queryByRole("article")).toBeNull();
});
