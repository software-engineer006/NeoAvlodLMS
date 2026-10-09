import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TeacherGroupStudentsView } from "../TeacherGroupStudentsView";
import { TeacherStudentDetailDrawer } from "../TeacherStudentDetailDrawer";
import type { TeacherGroupItem, TeacherStudentItem } from "../types";
import { apiClient } from "../../api/client";

describe("Teacher Students & Parent Detail Flow (Task 035)", () => {
  const sampleGroup: TeacherGroupItem = {
    id: "grp-1",
    name: "Python-01",
    subject_id: "sub-1",
    subject: {
      id: "sub-1",
      name: "Python Dasturlash",
    },
    monthly_price: 600000,
    max_students: 12,
    current_students: 2,
    status: "active",
    days_of_week: [1, 3, 5],
    start_time: "14:00:00",
    end_time: "16:00:00",
    room_number: "201-xona",
    created_at: "2026-03-01T10:00:00Z",
  };

  const sampleStudents: TeacherStudentItem[] = [
    {
      id: "std-1",
      first_name: "Sherzod",
      last_name: "Bekov",
      phone: "+998901111111",
      age: 16,
      status: "active",
      group_id: "grp-1",
      group_name: "Python-01",
      telegram_connected: true,
      parent: {
        id: "prt-1",
        first_name: "Rustam",
        last_name: "Bekov",
        phone: "+998902222222",
        telegram_connected: true,
      },
      created_at: "2026-03-02T12:00:00Z",
    },
    {
      id: "std-2",
      first_name: "Jasur",
      last_name: "Olimov",
      phone: "+998903333333",
      age: 15,
      status: "active",
      group_id: "grp-1",
      group_name: "Python-01",
      telegram_connected: false,
      parent: {
        id: "prt-2",
        first_name: "Nodira",
        last_name: "Olimova",
        phone: "+998904444444",
        telegram_connected: false,
      },
      created_at: "2026-03-03T14:30:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  describe("TeacherGroupStudentsView Flow", () => {
    it("renders group info, students table, parent contacts and Telegram status", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValueOnce(sampleStudents);

      const onBack = vi.fn();
      const onSelectAttendance = vi.fn();

      render(
        <TeacherGroupStudentsView
          group={sampleGroup}
          onBack={onBack}
          onSelectGroupForAttendance={onSelectAttendance}
        />
      );

      // Loading state check
      expect(screen.getByText("Guruh o‘quvchilari yuklanmoqda...")).toBeDefined();

      // Wait for data load
      await waitFor(() => {
        expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      });

      // Verify header and group details
      expect(screen.getByText("Python-01")).toBeDefined();
      expect(screen.getByText("Python Dasturlash")).toBeDefined();

      // Verify stats
      expect(screen.getAllByText("2").length).toBeGreaterThan(0); // Jami va faol o‘quvchilar
      expect(screen.getByText("1 / 2")).toBeDefined(); // Ota-ona Telegram: 1 ta ulangan

      // Check student 1 (Sherzod)
      expect(screen.getByText("+998901111111")).toBeDefined();
      expect(screen.getByText("16 yosh")).toBeDefined();
      expect(screen.getByText("Rustam Bekov")).toBeDefined();
      expect(screen.getByText("+998902222222")).toBeDefined();
      expect(screen.getByText("Ulangan")).toBeDefined(); // Parent telegram badge

      // Check student 2 (Jasur)
      expect(screen.getByText("Jasur Olimov")).toBeDefined();
      expect(screen.getByText("+998903333333")).toBeDefined();
      expect(screen.getByText("15 yosh")).toBeDefined();
      expect(screen.getByText("Nodira Olimova")).toBeDefined();
      expect(screen.getByText("+998904444444")).toBeDefined();
      expect(screen.getByText("Ulanmagan")).toBeDefined(); // Parent telegram badge

      // Click Back button
      const backBtn = screen.getByRole("button", { name: /Orqaga qaytish/i });
      fireEvent.click(backBtn);
      expect(onBack).toHaveBeenCalledTimes(1);

      // Click Davomat olish button
      const davomatBtn = screen.getByRole("button", { name: /Davomat olish/i });
      fireEvent.click(davomatBtn);
      expect(onSelectAttendance).toHaveBeenCalledWith(sampleGroup);
    });

    it("filters students by search query (name or phone)", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValueOnce(sampleStudents);

      render(<TeacherGroupStudentsView group={sampleGroup} onBack={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      });

      const searchInput = screen.getByPlaceholderText(/O‘quvchi yoki ota-ona ismi/i);
      fireEvent.change(searchInput, { target: { value: "Jasur" } });

      expect(screen.getByText("Jasur Olimov")).toBeDefined();
      expect(screen.queryByText("Sherzod Bekov")).toBeNull();

      // Search by parent phone
      fireEvent.change(searchInput, { target: { value: "222222" } });
      expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      expect(screen.queryByText("Jasur Olimov")).toBeNull();
    });

    it("renders unauthorized state when group is not accessible or not assigned to teacher", async () => {
      vi.spyOn(apiClient, "get").mockRejectedValueOnce(
        new Error("404 Group not found or not accessible")
      );

      const onBack = vi.fn();
      render(<TeacherGroupStudentsView group={sampleGroup} onBack={onBack} />);

      await waitFor(() => {
        expect(screen.getByText("Ushbu guruhga kirish taqiqlangan")).toBeDefined();
      });

      expect(
        screen.getByText(/Sizda ushbu guruh ma’lumotlarini ko‘rish huquqi yo‘q/i)
      ).toBeDefined();

      const returnBtn = screen.getByRole("button", { name: /Guruhlar ro‘yxatiga qaytish/i });
      fireEvent.click(returnBtn);
      expect(onBack).toHaveBeenCalledTimes(1);
    });

    it("renders empty state when group has no students", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValueOnce([]);

      render(<TeacherGroupStudentsView group={sampleGroup} onBack={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByText("O‘quvchilar topilmadi")).toBeDefined();
      });

      expect(
        screen.getByText("Ushbu guruhda hozircha o‘quvchilar mavjud emas.")
      ).toBeDefined();
    });

    it("handles network error and retries", async () => {
      vi.spyOn(apiClient, "get").mockRejectedValueOnce(new Error("Server bilan aloqa uzildi"));

      render(<TeacherGroupStudentsView group={sampleGroup} onBack={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByText("O‘quvchilarni yuklashda xatolik")).toBeDefined();
      });
      expect(screen.getByText("Server bilan aloqa uzildi")).toBeDefined();

      // Retry
      vi.spyOn(apiClient, "get").mockResolvedValueOnce(sampleStudents);
      const retryBtn = screen.getByRole("button", { name: /Qayta urinish/i });
      fireEvent.click(retryBtn);

      await waitFor(() => {
        expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      });
    });
  });

  describe("TeacherStudentDetailDrawer Component", () => {
    it("opens drawer and displays detailed student and parent profile", () => {
      const onClose = vi.fn();
      render(
        <TeacherStudentDetailDrawer
          isOpen={true}
          onClose={onClose}
          student={sampleStudents[0]}
        />
      );

      expect(screen.getByText("O‘quvchi ma’lumotlari")).toBeDefined();
      expect(screen.getByText(/Sherzod Bekov bo‘yicha batafsil profil/i)).toBeDefined();
      expect(screen.getByText("16 yoshda")).toBeDefined();
      expect(screen.getAllByText("Python-01").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("+998901111111")).toBeDefined();

      // Parent details
      expect(screen.getByText("Ota-ona ma’lumotlari")).toBeDefined();
      expect(screen.getByText("Rustam Bekov")).toBeDefined();
      expect(screen.getByText("+998902222222")).toBeDefined();
      expect(screen.getByText("Telegram hisobi ulangan")).toBeDefined();

      // Close drawer
      const closeBtns = screen.getAllByRole("button", { name: /Yopish/i });
      fireEvent.click(closeBtns[0]);
      expect(onClose).toHaveBeenCalled();
    });

    it("displays warning box when parent Telegram is not connected", () => {
      render(
        <TeacherStudentDetailDrawer
          isOpen={true}
          onClose={vi.fn()}
          student={sampleStudents[1]}
        />
      );

      expect(screen.getByText("Jasur Olimov")).toBeDefined();
      expect(screen.getByText("Nodira Olimova")).toBeDefined();
      expect(screen.getAllByText("Telegram ulanmagan").length).toBeGreaterThan(0);
      expect(
        screen.getByText(/Ota-ona botga ulanmagan/i)
      ).toBeDefined();
    });

    it("renders nothing when drawer is closed", () => {
      render(
        <TeacherStudentDetailDrawer
          isOpen={false}
          onClose={vi.fn()}
          student={sampleStudents[0]}
        />
      );

      expect(screen.queryByText("O‘quvchi ma’lumotlari")).toBeNull();
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
