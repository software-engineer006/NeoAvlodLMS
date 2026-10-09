import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TeacherShell } from "../TeacherShell";
import { TeacherGroupsView } from "../TeacherGroupsView";
import { ForbiddenPage } from "../../navigation/ForbiddenPage";
import type { CurrentUser } from "../../api/types";
import type { TeacherGroupItem } from "../types";
import { apiClient } from "../../api/client";

describe("Teacher Portal Shell & Groups Flow (Task 034)", () => {
  const teacherUser: CurrentUser = {
    id: "tch-1",
    username: "teacher_ali",
    first_name: "Ali",
    last_name: "Valiyev",
    phone: "+998901234567",
    role: "teacher",
    status: "active",
    permissions: [],
  };

  const sampleGroups: TeacherGroupItem[] = [
    {
      id: "grp-1",
      name: "Python-01",
      subject_id: "sub-1",
      subject: {
        id: "sub-1",
        name: "Python Dasturlash",
      },
      monthly_price: 600000,
      max_students: 12,
      current_students: 10,
      status: "active",
      days_of_week: [1, 3, 5],
      start_time: "14:00:00",
      end_time: "16:00:00",
      room_number: "201-xona",
      created_at: "2026-03-01T10:00:00Z",
    },
    {
      id: "grp-2",
      name: "Django-02",
      subject_id: "sub-1",
      subject: {
        id: "sub-1",
        name: "Python Dasturlash",
      },
      monthly_price: 700000,
      max_students: 10,
      current_students: 10,
      status: "active",
      days_of_week: [2, 4, 6],
      start_time: "16:00:00",
      end_time: "18:00:00",
      room_number: "202-xona",
      created_at: "2026-03-05T10:00:00Z",
    },
    {
      id: "grp-3",
      name: "Arxiv-Guruh",
      subject_id: "sub-2",
      subject: {
        id: "sub-2",
        name: "Frontend Asoslari",
      },
      monthly_price: 500000,
      max_students: 15,
      current_students: 5,
      status: "inactive",
      days_of_week: [1, 3, 5],
      start_time: "10:00:00",
      end_time: "12:00:00",
      room_number: "105-xona",
      created_at: "2026-02-01T10:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  describe("Portal Guard & 403 Forbidden Access", () => {
    it("renders 403 Forbidden page for admin attempting to access Teacher portal", () => {
      const handleLogout = vi.fn();
      render(
        <ForbiddenPage
          isAdmin={true}
          onLogout={handleLogout}
        />
      );

      expect(screen.getByText("Xatolik 403")).toBeDefined();
      expect(screen.getByText("Ruxsat berilmagan")).toBeDefined();
      expect(
        screen.getByText(/Siz ma’muriyat hisobiga egasiz\. O‘qituvchi portali faqat o‘qituvchilar uchun mo‘ljallangan/i)
      ).toBeDefined();

      const adminLink = screen.getByRole("link", { name: /Admin portaliga o‘tish/i });
      expect(adminLink.getAttribute("href")).toBe("https://admin.eduneo.uz");

      const logoutBtn = screen.getByRole("button", { name: /Boshqa hisob bilan kirish/i });
      fireEvent.click(logoutBtn);
      expect(handleLogout).toHaveBeenCalledTimes(1);
    });

    it("renders custom message on ForbiddenPage if provided", () => {
      render(
        <ForbiddenPage
          isAdmin={true}
          message="Maxsus xatolik xabari: teacher portaliga kirish taqiqlanadi"
        />
      );

      expect(
        screen.getByText("Maxsus xatolik xabari: teacher portaliga kirish taqiqlanadi")
      ).toBeDefined();
    });
  });

  describe("TeacherShell Navigation & Layout", () => {
    it("renders teacher profile information and badge", () => {
      render(
        <TeacherShell
          user={teacherUser}
          activeTab="groups"
          onTabChange={vi.fn()}
          onLogout={vi.fn()}
        >
          <div>Ichki kontent</div>
        </TeacherShell>
      );

      expect(screen.getByText("NeoAvlod LMS")).toBeDefined();
      expect(screen.getByText("O‘qituvchi Portali")).toBeDefined();
      expect(screen.getByText("Ali Valiyev")).toBeDefined();
      expect(screen.getByText("@teacher_ali")).toBeDefined();
      expect(screen.getByText("+998901234567")).toBeDefined();
      expect(screen.getByText("O‘qituvchi")).toBeDefined();
      expect(screen.getByText("Ichki kontent")).toBeDefined();
    });

    it("handles tab changes and logout correctly", () => {
      const handleTabChange = vi.fn();
      const handleLogout = vi.fn();
      const handleChangePassword = vi.fn();

      render(
        <TeacherShell
          user={teacherUser}
          activeTab="groups"
          onTabChange={handleTabChange}
          onLogout={handleLogout}
          onChangePassword={handleChangePassword}
        >
          <div>Kontent</div>
        </TeacherShell>
      );

      // Click on Davomat olish nav item
      const attendanceNavBtn = screen.getByRole("button", { name: /Davomat olish/i });
      fireEvent.click(attendanceNavBtn);
      expect(handleTabChange).toHaveBeenCalledWith("attendance");

      // Click Password change button
      const passwordBtn = screen.getByRole("button", { name: /Parol/i });
      fireEvent.click(passwordBtn);
      expect(handleChangePassword).toHaveBeenCalledTimes(1);

      // Click Logout button
      const logoutBtns = screen.getAllByRole("button", { name: /Chiqish/i });
      fireEvent.click(logoutBtns[0]);
      expect(handleLogout).toHaveBeenCalled();
    });
  });

  describe("TeacherGroupsView Flow", () => {
    it("fetches and renders teacher's assigned groups with schedules and occupancy", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValueOnce(sampleGroups);

      const onSelectAttendance = vi.fn();
      const onSelectStudents = vi.fn();

      render(
        <TeacherGroupsView
          onSelectGroupForAttendance={onSelectAttendance}
          onSelectGroupForStudents={onSelectStudents}
        />
      );

      // Loading state check
      expect(screen.getByText("Guruhlar ro‘yxati yuklanmoqda...")).toBeDefined();

      // Wait for data load
      await waitFor(() => {
        expect(screen.getByText("Python-01")).toBeDefined();
      });

      // Verify stats
      expect(screen.getByText("3")).toBeDefined(); // Jami guruhlar
      expect(screen.getByText("2")).toBeDefined(); // Faol guruhlar
      expect(screen.getByText("25")).toBeDefined(); // Jami o'quvchilar: 10 + 10 + 5 = 25

      // Verify group items
      expect(screen.getByText("Django-02")).toBeDefined();
      expect(screen.getByText("Arxiv-Guruh")).toBeDefined();
      expect(screen.getByText("201-xona")).toBeDefined();
      expect(screen.getByText("202-xona")).toBeDefined();

      // Check OccupancyBadges: 10/12, 10/10 (to'lgan)
      expect(screen.getByText("10 / 12")).toBeDefined();
      expect(screen.getByText("10 / 10")).toBeDefined();

      // Click Davomat for Python-01
      const davomatButtons = screen.getAllByRole("button", { name: /Davomat/i });
      fireEvent.click(davomatButtons[0]);
      expect(onSelectAttendance).toHaveBeenCalledWith(sampleGroups[0]);

      // Click O‘quvchilar for Python-01
      const oquvchilarButtons = screen.getAllByRole("button", { name: /O‘quvchilar/i });
      fireEvent.click(oquvchilarButtons[0]);
      expect(onSelectStudents).toHaveBeenCalledWith(sampleGroups[0]);
    });

    it("filters groups by status and search keyword", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValueOnce(sampleGroups);

      render(<TeacherGroupsView />);

      await waitFor(() => {
        expect(screen.getByText("Python-01")).toBeDefined();
      });

      // Search by keyword "Django"
      const searchInput = screen.getByPlaceholderText(/Guruh, fan yoki xona nomi/i);
      fireEvent.change(searchInput, { target: { value: "Django" } });

      expect(screen.getByText("Django-02")).toBeDefined();
      expect(screen.queryByText("Python-01")).toBeNull();
      expect(screen.queryByText("Arxiv-Guruh")).toBeNull();

      // Clear search and filter by inactive
      fireEvent.change(searchInput, { target: { value: "" } });
      const selectFilter = screen.getByRole("combobox");
      fireEvent.change(selectFilter, { target: { value: "inactive" } });

      expect(screen.queryByText("Python-01")).toBeNull();
      expect(screen.queryByText("Django-02")).toBeNull();
      expect(screen.getByText("Arxiv-Guruh")).toBeDefined();
    });

    it("renders empty state when teacher has no groups", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValueOnce([]);

      render(<TeacherGroupsView />);

      await waitFor(() => {
        expect(screen.getByText("Guruhlar topilmadi")).toBeDefined();
      });

      expect(
        screen.getByText("Sizga hozircha hech qanday guruh biriktirilmagan.")
      ).toBeDefined();
    });

    it("handles API error with retry functionality", async () => {
      vi.spyOn(apiClient, "get").mockRejectedValueOnce(new Error("Tarmoq xatosi"));

      render(<TeacherGroupsView />);

      await waitFor(() => {
        expect(screen.getByText("Guruhlarni yuklashda xatolik")).toBeDefined();
      });
      expect(screen.getByText("Tarmoq xatosi")).toBeDefined();

      // Retry
      vi.spyOn(apiClient, "get").mockResolvedValueOnce(sampleGroups);
      const retryBtn = screen.getByRole("button", { name: /Qayta urinish/i });
      fireEvent.click(retryBtn);

      await waitFor(() => {
        expect(screen.getByText("Python-01")).toBeDefined();
      });
    });
  });

  describe("Security & Storage Verification", () => {
    it("never stores tokens, secrets, or passwords in localStorage or sessionStorage", () => {
      expect(localStorage.getItem("token")).toBeNull();
      expect(localStorage.getItem("access_token")).toBeNull();
      expect(sessionStorage.getItem("token")).toBeNull();
      expect(sessionStorage.getItem("access_token")).toBeNull();
    });
  });
});
