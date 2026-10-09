import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MonthlyAttendanceHistoryView } from "../MonthlyAttendanceHistoryView";
import { apiClient } from "../../api/client";
import type { GroupMonthlyAttendanceHistoryResponse } from "../types";

const groups = [{ id: "g1", name: "Python" }, { id: "g2", name: "English" }];
const history: GroupMonthlyAttendanceHistoryResponse = {
  group_id: "g1", group_name: "Python", month: "2026-10", dates: ["2026-10-06"],
  records: [{ attendance_id: "a1", student_id: "s1", student_name: "Test Student", date: "2026-10-06", status: "late", note: "Traffic" }],
  students_summary: [{ student_id: "s1", student_name: "Test Student", present_count: 0, late_count: 1, absent_count: 0, attended_count: 1, total_lessons: 1 }],
  summary: { total_lessons: 1, total_records: 1, present_count: 0, late_count: 1, absent_count: 0 },
};
beforeEach(() => vi.restoreAllMocks());
describe("Monthly attendance", () => {
  it("shows the whole month, notes, neutral gaps and denies unauthorized profile", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(history);
    render(<MonthlyAttendanceHistoryView portal="admin" groups={groups} initialGroupId="g1" initialMonth="2026-10" />);
    await screen.findByText("Test Student");
    expect(screen.getByText("31")).toBeDefined();
    expect(screen.getByLabelText("2026-10-06: Kech qoldi")).toBeDefined();
    expect(screen.getByLabelText("2026-10-07: Dars belgilanmagan")).toBeDefined();
    expect(screen.getByText("Traffic")).toBeDefined();
    fireEvent.click(screen.getByText("Test Student"));
    expect(get.mock.calls.every(([url]) => !url.includes("/students/"))).toBe(true);
  });
  it("ignores an old group response and handles year boundaries", async () => {
    let resolveOld!: (data: typeof history) => void;
    const get = vi.spyOn(apiClient, "get")
      .mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }))
      .mockResolvedValue({ ...history, group_id: "g2", students_summary: [{ ...history.students_summary[0], student_name: "New Student" }] });
    render(<MonthlyAttendanceHistoryView portal="teacher" groups={groups} initialGroupId="g1" initialMonth="2027-01" />);
    fireEvent.change(screen.getByLabelText("Guruhni tanlang"), { target: { value: "g2" } });
    await screen.findByText("New Student");
    resolveOld(history);
    await waitFor(() => expect(screen.queryByText("Test Student")).toBeNull());
    fireEvent.click(screen.getByTitle("Oldingi oy"));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith("/api/v1/teacher/groups/g2/attendance/history", { params: { month: "2026-12" } }));
  });
  it("shows errors, retries and represents an empty month", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValueOnce(new Error("Network failed"))
      .mockResolvedValue({ ...history, dates: [], records: [], students_summary: [], summary: { ...history.summary, total_lessons: 0 } });
    render(<MonthlyAttendanceHistoryView portal="teacher" groups={groups} initialGroupId="g1" initialMonth="2026-02" />);
    await screen.findByText("Network failed");
    fireEvent.click(screen.getByRole("button", { name: /Qayta/i }));
    await screen.findByText(/hali yakunlangan davomat darslari mavjud emas/);
    expect(screen.queryByRole("table")).toBeNull();
  });
});
