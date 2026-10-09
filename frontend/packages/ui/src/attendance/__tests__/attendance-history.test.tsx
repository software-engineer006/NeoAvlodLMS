import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AttendanceBadge } from "../AttendanceBadge";
import { AdminAttendanceView } from "../AdminAttendanceView";
import type { CurrentUser } from "../../api/types";
import type { AdminAttendanceItem } from "../types";
import type { GroupItem } from "../../academic/types";
import { apiClient } from "../../api/client";

describe("Admin Attendance History (Task 032)", () => {
  const adminUser: CurrentUser = {
    id: "ad-1",
    username: "attendance_admin",
    first_name: "Aziz",
    last_name: "Soliyev",
    phone: "+998901234567",
    role: "admin",
    status: "active",
    permissions: ["attendance:read"],
  };

  const sampleGroups: GroupItem[] = [
    {
      id: "grp-1",
      name: "Python Pro - 101",
      subject_id: "sub-1",
      teacher_id: "tch-1",
      monthly_price: "600000.00",
      max_students: 12,
      current_students: 8,
      status: "active",
      days_of_week: [1, 3, 5],
      start_time: "09:00:00",
      end_time: "11:00:00",
      room_number: "201-xona",
      created_at: "2026-02-01T10:00:00Z",
      updated_at: "2026-02-01T10:00:00Z",
      subject: { id: "sub-1", name: "Python Backend", is_active: true },
      teacher: {
        id: "tch-1",
        first_name: "Dilshod",
        last_name: "Raximov",
        phone: "+998901234567",
        status: "active",
      },
    },
  ];

  const sampleRecords: AdminAttendanceItem[] = [
    {
      attendance_id: "att-1",
      date: "2026-03-01",
      group_id: "grp-1",
      group_name: "Python Pro - 101",
      teacher_id: "tch-1",
      teacher_name: "Dilshod Raximov",
      student_id: "st-1",
      student_name: "Jasur Bekmurodov",
      status: "present",
      note: "Darsga o‘z vaqtida keldi",
      marked_at: "2026-03-01T09:05:00Z",
      finalized: true,
      batch_id: "b-1",
    },
    {
      attendance_id: "att-2",
      date: "2026-03-01",
      group_id: "grp-1",
      group_name: "Python Pro - 101",
      teacher_id: "tch-1",
      teacher_name: "Dilshod Raximov",
      student_id: "st-2",
      student_name: "Kamola Ismoilova",
      status: "absent",
      note: "Sababsiz dars qoldirdi",
      marked_at: "2026-03-01T09:05:00Z",
      finalized: true,
      batch_id: "b-1",
    },
    {
      attendance_id: "att-3",
      date: "2026-03-01",
      group_id: "grp-1",
      group_name: "Python Pro - 101",
      teacher_id: "tch-1",
      teacher_name: "Dilshod Raximov",
      student_id: "st-3",
      student_name: "Sardor Aliyev",
      status: "late",
      note: "15 daqiqa kechikib kirdi",
      marked_at: "2026-03-01T09:20:00Z",
      finalized: true,
      batch_id: "b-1",
    },
  ];

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  describe("AttendanceBadge Component", () => {
    it("renders Bor, Yo‘q, and Kechikdi statuses correctly", () => {
      const { rerender } = render(<AttendanceBadge status="present" />);
      expect(screen.getByText("Bor")).toBeDefined();

      rerender(<AttendanceBadge status="absent" />);
      expect(screen.getByText("Yo‘q")).toBeDefined();

      rerender(<AttendanceBadge status="late" />);
      expect(screen.getByText("Kechikdi")).toBeDefined();
    });
  });

  describe("AdminAttendanceView Component", () => {
    it("fetches and renders attendance records in readonly table with stats", async () => {
      vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
        if (url.includes("/api/v1/admin/groups")) {
          return Promise.resolve({ items: sampleGroups, total: 1, page: 1, page_size: 10 });
        }
        if (url.includes("/api/v1/admin/staff")) {
          return Promise.resolve({
            items: [
              {
                id: "tch-1",
                first_name: "Dilshod",
                last_name: "Raximov",
                phone: "+998901234567",
                role: "teacher",
                status: "active",
              },
            ],
            total: 1,
            page: 1,
            page_size: 10,
          });
        }
        if (url.includes("/api/v1/admin/attendance")) {
          return Promise.resolve({
            items: sampleRecords,
            total: 3,
            page: 1,
            page_size: 15,
          });
        }
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      });

      render(<AdminAttendanceView currentUser={adminUser} defaultTab="list" />);

      await waitFor(() => {
        expect(screen.getByText("Davomat tarixi")).toBeDefined();
        expect(screen.getByText("Jasur Bekmurodov")).toBeDefined();
        expect(screen.getByText("Kamola Ismoilova")).toBeDefined();
        expect(screen.getByText("Sardor Aliyev")).toBeDefined();
      });

      // Status badges and stats
      expect(screen.getAllByText("Bor").length).toBeGreaterThanOrEqual(2);
      expect(screen.getAllByText("Yo‘q").length).toBeGreaterThanOrEqual(2);
      expect(screen.getAllByText("Kechikdi").length).toBeGreaterThanOrEqual(2);

      // Notes
      expect(screen.getByText("Darsga o‘z vaqtida keldi")).toBeDefined();
      expect(screen.getByText("Sababsiz dars qoldirdi")).toBeDefined();
      expect(screen.getByText("15 daqiqa kechikib kirdi")).toBeDefined();

      // Finalized indicators (1 column header + 3 rows)
      expect(screen.getAllByText("Yakunlangan").length).toBe(4);

      // Verify strictly readonly: NO attendance taking buttons or inputs
      expect(screen.queryByRole("button", { name: /Davomat olish/i })).toBeNull();
      expect(screen.queryByRole("button", { name: /Saqlash/i })).toBeNull();
      expect(screen.queryByRole("button", { name: /Yakunlash/i })).toBeNull();

      // Security check: zero secrets in storage
      expect(localStorage.length).toBe(0);
      expect(sessionStorage.length).toBe(0);
    });

    it("handles filters and reset filters button", async () => {
      const getSpy = vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
        if (url.includes("/api/v1/admin/attendance")) {
          return Promise.resolve({
            items: [sampleRecords[0]],
            total: 1,
            page: 1,
            page_size: 15,
          });
        }
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      });

      render(<AdminAttendanceView currentUser={adminUser} defaultTab="list" />);

      await waitFor(() => {
        expect(screen.getByText("Jasur Bekmurodov")).toBeDefined();
      });

      // Click "Bugun" quick button
      const todayBtn = screen.getByRole("button", { name: "Bugun" });
      fireEvent.click(todayBtn);

      await waitFor(() => {
        expect(getSpy).toHaveBeenCalled();
      });

      // Clear filters button appears when filter is active
      const clearBtn = screen.getByRole("button", { name: "Filtrlarni tozalash" });
      expect(clearBtn).toBeDefined();
      fireEvent.click(clearBtn);

      await waitFor(() => {
        expect(screen.queryByRole("button", { name: "Filtrlarni tozalash" })).toBeNull();
      });
    });
  });
});
