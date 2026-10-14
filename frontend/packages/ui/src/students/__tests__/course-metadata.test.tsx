import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { apiClient } from "../../api/client";
import { EnrollmentMetadataEditor } from "../EnrollmentMetadataEditor";
import { StudentCourseMetadata } from "../../components/StudentCourseMetadata";
import { StudentModal } from "../StudentModal";
import type { StudentDetailItem } from "../types";

const group = { id: "g", name: "Namuna kurs", status: "active" as const };
const course = { group, is_active: true, level: "Elementary", mygov_status: "o‘tdi", notes: "Namuna izoh" };
const pupil: StudentDetailItem = { id: "p", first_name: "Namuna", last_name: "O‘quvchi", phone: null,
  age: null, status: "active", group_id: "g", group, parent_id: null, parent: null,
  telegram_connected: false, created_at: "2026-10-14T00:00:00Z", school_grade: "7", school_name: "Namuna maktab" };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("course editor validates bounds, clears explicit fields and keeps writes tied to selected membership", async () => {
  const patch = vi.spyOn(apiClient, "patch").mockResolvedValue(pupil); const saved = vi.fn();
  render(<EnrollmentMetadataEditor studentId="p" enrollment={course} onSaved={saved} onClose={vi.fn()} />);
  expect((screen.getByLabelText("Daraja") as HTMLInputElement).maxLength).toBe(150);
  expect((screen.getByLabelText("Kurs izohi") as HTMLTextAreaElement).maxLength).toBe(4000);
  fireEvent.change(screen.getByLabelText("Daraja"), { target: { value: "" } });
  fireEvent.change(screen.getByLabelText("MyGov holati"), { target: { value: "  pullik  " } });
  fireEvent.change(screen.getByLabelText("Kurs izohi"), { target: { value: "" } });
  fireEvent.submit(screen.getByRole("form"));
  await waitFor(() => expect(patch).toHaveBeenCalledWith("/api/v1/admin/students/p/groups/g", { level: null, mygov_status: "pullik", notes: null }));
  expect(saved).toHaveBeenCalledWith(pupil);
});

it("metadata presentation renders untrusted notes as escaped text", () => {
  const notes = '<img src=x onerror="alert(1)">';
  const { container } = render(<StudentCourseMetadata {...course} notes={notes} />);
  expect(screen.getByText(notes)).toBeDefined(); expect(container.querySelector("img")).toBeNull();
  expect(screen.getByText("Elementary")).toBeDefined(); expect(screen.getByText("o‘tdi")).toBeDefined();
});

it("school form preserves blanks explicitly without erasing unrelated profile or parent fields", async () => {
  const patch = vi.spyOn(apiClient, "patch").mockResolvedValue(pupil);
  render(<StudentModal isOpen onClose={vi.fn()} student={pupil} onSuccess={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Maktabi"), { target: { value: "" } });
  fireEvent.change(screen.getByLabelText("Sinf"), { target: { value: "8-sinf" } });
  fireEvent.submit(screen.getByLabelText("Sinf").closest("form")!);
  await waitFor(() => expect(patch).toHaveBeenCalledWith("/api/v1/admin/students/p", expect.objectContaining({ school_name: null, school_grade: "8-sinf" })));
});
