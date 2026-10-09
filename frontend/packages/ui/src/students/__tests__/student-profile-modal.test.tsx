import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { StudentProfileModal, StudentDetailDrawer } from "../StudentDetailDrawer";
import { StudentsManagementView } from "../StudentsManagementView";
import { TeacherGroupStudentsView } from "../../teacher/TeacherGroupStudentsView";
import { TeacherStudentProfileModal, TeacherStudentDetailDrawer } from "../../teacher/TeacherStudentDetailDrawer";
import type { CurrentUser } from "../../api/types";
import type { StudentDetailItem, StudentItem } from "../types";
import type { TeacherGroupItem, TeacherStudentItem } from "../../teacher/types";
import { PERMISSIONS } from "../../navigation/permissions";
import { apiClient } from "../../api/client";

describe("Student Profile & Monthly Attendance Modal (Task 057)", () => {
  const fullAdminUser: CurrentUser = {
    id: "admin-1",
    username: "admin_user",
    first_name: "Aziz",
    last_name: "Rahimov",
    phone: "+998901234567",
    role: "admin",
    status: "active",
    permissions: [
      PERMISSIONS.STUDENTS_READ,
      PERMISSIONS.STUDENTS_EDIT,
      PERMISSIONS.ATTENDANCE_READ,
    ],
  };

  const adminWithoutAttendanceUser: CurrentUser = {
    id: "admin-no-att",
    username: "admin_no_att",
    first_name: "Nodir",
    last_name: "Zokirov",
    phone: "+998907654321",
    role: "admin",
    status: "active",
    permissions: [PERMISSIONS.STUDENTS_READ, PERMISSIONS.STUDENTS_EDIT],
  };

  const sampleStudentDetailWithStats: StudentDetailItem = {
    id: "std-100",
    first_name: "Sanjar",
    last_name: "Qodirov",
    phone: "+998901112233",
    age: 16,
    status: "active",
    group_id: "grp-1",
    parent_id: "prt-1",
    telegram_connected: false,
    created_at: "2026-01-15T09:00:00Z",
    parent: {
      id: "prt-1",
      first_name: "Olim",
      last_name: "Qodirov",
      phone: "+998909998877",
      telegram_connected: false,
      created_at: "2026-01-15T09:00:00Z",
      telegram_link: {
        deep_link: "https://t.me/eduneo_admin_bot?start=prt_tok_999",
        expires_at: "2026-04-01T00:00:00Z",
        is_expired: false,
      },
    },
    group: {
      id: "grp-1",
      name: "Frontend React - 01",
      status: "active",
      subject_id: "sub-1",
      subject_name: "Veb Dasturlash",
      teacher_id: "tch-1",
      teacher_name: "Javohir Aliyev",
      days_of_week: [1, 3, 5],
      start_time: "14:00:00",
      end_time: "16:00:00",
      room_number: "305-xona",
      monthly_price: 650000,
    },
    telegram_link: {
      deep_link: "https://t.me/eduneo_admin_bot?start=std_tok_888",
      expires_at: "2026-04-01T00:00:00Z",
      is_expired: false,
    },
    attendance_stats: {
      month: "2026-03",
      present_count: 10,
      late_count: 2,
      absent_count: 1,
      attended_count: 12,
      total_lessons: 13,
    },
  };

  const sampleStudentItem: StudentItem = {
    id: "std-100",
    first_name: "Sanjar",
    last_name: "Qodirov",
    phone: "+998901112233",
    age: 16,
    status: "active",
    group_id: "grp-1",
    parent_id: "prt-1",
    telegram_connected: false,
    created_at: "2026-01-15T09:00:00Z",
    parent: {
      id: "prt-1",
      first_name: "Olim",
      last_name: "Qodirov",
      phone: "+998909998877",
      telegram_connected: false,
      created_at: "2026-01-15T09:00:00Z",
    },
    group: {
      id: "grp-1",
      name: "Frontend React - 01",
      status: "active",
    },
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("StudentProfileModal (Admin Portal)", () => {
    it("renders complete student profile with modal dialog role and organized sections", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue(sampleStudentDetailWithStats);

      render(
        <StudentProfileModal
          isOpen={true}
          onClose={vi.fn()}
          studentId="std-100"
          currentUser={fullAdminUser}
          onEdit={vi.fn()}
          onTransfer={vi.fn()}
          onStatusChanged={vi.fn()}
          onDeleted={vi.fn()}
        />
      );

      // Verify accessible dialog
      const dialog = await screen.findByRole("dialog");
      expect(dialog).toBeDefined();

      // 1. Student Profile
      expect(screen.getAllByText("Sanjar Qodirov").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("16 yoshda")).toBeDefined();
      expect(screen.getByText("+998901112233")).toBeDefined();
      const phoneLink = screen.getByText("+998901112233").closest("a");
      expect(phoneLink?.getAttribute("href")).toBe("tel:+998901112233");

      // 2. Group & Lesson details
      expect(screen.getByText("Frontend React - 01")).toBeDefined();
      expect(screen.getByText("Veb Dasturlash")).toBeDefined();
      expect(screen.getByText("Javohir Aliyev")).toBeDefined();
      expect(screen.getByText("Dush / Chor / Juma")).toBeDefined();
      expect(screen.getByText(/14:00/)).toBeDefined();
      expect(screen.getByText("305-xona")).toBeDefined();
      expect(screen.getByText(/650\s*000\s*so‘m/i)).toBeDefined();

      // 3. Parent & Contacts
      expect(screen.getByText("Olim Qodirov")).toBeDefined();
      expect(screen.getByText("+998909998877")).toBeDefined();

      // 4. Telegram deep links
      expect(screen.getByText("https://t.me/eduneo_admin_bot?start=std_tok_888")).toBeDefined();
      expect(screen.getByText("https://t.me/eduneo_admin_bot?start=prt_tok_999")).toBeDefined();

      // 5. Attendance Statistics Cards
      expect(screen.getByText("Oylik davomat statistikasi")).toBeDefined();
      expect(screen.getByText("Kelgan")).toBeDefined();
      expect(screen.getByText("10")).toBeDefined(); // present_count
      expect(screen.getByText("Kech qoldi")).toBeDefined();
      expect(screen.getByText("2")).toBeDefined(); // late_count
      expect(screen.getByText("Kelmagan")).toBeDefined();
      expect(screen.getByText("1")).toBeDefined(); // absent_count
      expect(screen.getByText("Jami darslar")).toBeDefined();
      expect(screen.getByText("13")).toBeDefined(); // total_lessons
      expect(screen.getByText("92%")).toBeDefined(); // (12 / 13) * 100 = 92%
    });

    it("supports alias export StudentDetailDrawer = StudentProfileModal", () => {
      expect(StudentDetailDrawer).toBe(StudentProfileModal);
    });

    it("changes month and fetches updated statistics when month buttons are clicked", async () => {
      const getSpy = vi.spyOn(apiClient, "get").mockResolvedValue(sampleStudentDetailWithStats);

      render(
        <StudentProfileModal
          isOpen={true}
          onClose={vi.fn()}
          studentId="std-100"
          currentUser={fullAdminUser}
          onEdit={vi.fn()}
          onTransfer={vi.fn()}
          onStatusChanged={vi.fn()}
          onDeleted={vi.fn()}
        />
      );

      await screen.findByRole("dialog");

      // Click previous month
      const prevBtn = await screen.findByRole("button", { name: "Oldingi oy" });
      fireEvent.click(prevBtn);

      await waitFor(() => {
        expect(getSpy).toHaveBeenCalledTimes(2);
      });

      // Click next month
      const nextBtn = screen.getByRole("button", { name: "Keyingi oy" });
      fireEvent.click(nextBtn);

      await waitFor(() => {
        expect(getSpy).toHaveBeenCalledTimes(3);
      });
    });

    it("hides attendance stats with friendly message when admin lacks ATTENDANCE_READ", async () => {
      const studentWithoutStats: StudentDetailItem = {
        ...sampleStudentDetailWithStats,
        attendance_stats: null,
      };
      vi.spyOn(apiClient, "get").mockResolvedValue(studentWithoutStats);

      render(
        <StudentProfileModal
          isOpen={true}
          onClose={vi.fn()}
          studentId="std-100"
          currentUser={adminWithoutAttendanceUser}
          onEdit={vi.fn()}
          onTransfer={vi.fn()}
          onStatusChanged={vi.fn()}
          onDeleted={vi.fn()}
        />
      );

      await screen.findByRole("dialog");

      // Profile is visible
      expect(screen.getAllByText("Sanjar Qodirov").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Olim Qodirov")).toBeDefined();

      // Attendance statistics is restricted
      expect(
        screen.getByText(/Davomat statistikasini ko‘rish uchun sizda yetarli ruxsat yo‘q/i)
      ).toBeDefined();
      expect(screen.queryByText("Kelgan")).toBeNull();
    });

    it("closes modal on Escape key press", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue(sampleStudentDetailWithStats);
      const onClose = vi.fn();

      render(
        <StudentProfileModal
          isOpen={true}
          onClose={onClose}
          studentId="std-100"
          currentUser={fullAdminUser}
          onEdit={vi.fn()}
          onTransfer={vi.fn()}
          onStatusChanged={vi.fn()}
          onDeleted={vi.fn()}
        />
      );

      await screen.findByRole("dialog");

      fireEvent.keyDown(window, { key: "Escape" });
      expect(onClose).toHaveBeenCalled();
    });
  });

  describe("Table Row Click & Action Event Propagation in StudentsManagementView", () => {
    it("opens profile modal when table row or student name is clicked", async () => {
      vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
        if (url.includes("/api/v1/admin/groups")) {
          return Promise.resolve({
            items: [
              {
                id: "grp-1",
                name: "Frontend React - 01",
                subject_id: "sub-1",
                teacher_id: "tch-1",
                monthly_price: 650000,
                max_students: 12,
                current_students: 1,
                status: "active",
                days_of_week: [1, 3, 5],
                start_time: "14:00:00",
                end_time: "16:00:00",
                room_number: "305-xona",
                created_at: "2026-01-01T00:00:00Z",
                updated_at: "2026-01-01T00:00:00Z",
                subject: { id: "sub-1", name: "Veb Dasturlash", is_active: true },
                teacher: {
                  id: "tch-1",
                  first_name: "Javohir",
                  last_name: "Aliyev",
                  phone: "+998901111111",
                  status: "active",
                },
              },
            ],
            total: 1,
            page: 1,
            page_size: 10,
          });
        }
        if (url.includes("/api/v1/admin/students/std-100")) {
          return Promise.resolve(sampleStudentDetailWithStats);
        }
        if (url.includes("/api/v1/admin/students")) {
          return Promise.resolve({
            items: [sampleStudentItem],
            total: 1,
            page: 1,
            page_size: 10,
          });
        }
        return Promise.resolve({ items: [], total: 0 });
      });

      render(<StudentsManagementView currentUser={fullAdminUser} />);

      await waitFor(() => {
        expect(screen.getByText("Sanjar Qodirov")).toBeDefined();
      });

      // Click on student name button
      const studentBtn = screen.getByRole("button", { name: /Sanjar Qodirov/i });
      fireEvent.click(studentBtn);

      // Verify modal opened
      await waitFor(() => {
        expect(screen.getByRole("dialog")).toBeDefined();
        expect(screen.getByText("Oylik davomat statistikasi")).toBeDefined();
      });
    });
  });

  describe("TeacherStudentProfileModal & TeacherGroupStudentsView (Teacher Portal)", () => {
    const teacherGroup: TeacherGroupItem = {
      id: "grp-1",
      name: "Frontend React - 01",
      subject_id: "sub-1",
      subject: { id: "sub-1", name: "Veb Dasturlash" },
      monthly_price: 650000,
      max_students: 12,
      current_students: 1,
      status: "active",
      days_of_week: [1, 3, 5],
      start_time: "14:00:00",
      end_time: "16:00:00",
      room_number: "305-xona",
      created_at: "2026-01-01T00:00:00Z",
    };

    const teacherStudent: TeacherStudentItem = {
      id: "std-100",
      first_name: "Sanjar",
      last_name: "Qodirov",
      phone: "+998901112233",
      age: 16,
      status: "active",
      group_id: "grp-1",
      group_name: "Frontend React - 01",
      telegram_connected: true,
      parent: {
        id: "prt-1",
        first_name: "Olim",
        last_name: "Qodirov",
        phone: "+998909998877",
        telegram_connected: true,
      },
      created_at: "2026-01-15T09:00:00Z",
      subject_name: "Veb Dasturlash",
      teacher_name: "Javohir Aliyev",
      days_of_week: [1, 3, 5],
      start_time: "14:00:00",
      end_time: "16:00:00",
      room_number: "305-xona",
      monthly_price: 650000,
      attendance_stats: {
        month: "2026-03",
        present_count: 8,
        late_count: 1,
        absent_count: 1,
        attended_count: 9,
        total_lessons: 10,
      },
    };

    it("supports alias export TeacherStudentDetailDrawer = TeacherStudentProfileModal", () => {
      expect(TeacherStudentDetailDrawer).toBe(TeacherStudentProfileModal);
    });

    it("renders teacher profile modal with attendance stats and schedule details", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue(teacherStudent);

      render(
        <TeacherStudentProfileModal
          isOpen={true}
          onClose={vi.fn()}
          student={teacherStudent}
        />
      );

      const dialog = await screen.findByRole("dialog");
      expect(dialog).toBeDefined();

      expect(screen.getAllByText("Sanjar Qodirov").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("16 yoshda")).toBeDefined();
      expect(screen.getAllByText("Frontend React - 01").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Veb Dasturlash")).toBeDefined();
      expect(screen.getByText("305-xona")).toBeDefined();

      // Attendance stats
      expect(screen.getByText("Oylik davomat statistikasi")).toBeDefined();
      expect(screen.getByText("Kelgan")).toBeDefined();
      expect(screen.getByText("8")).toBeDefined();
      expect(screen.getByText("Kech qoldi")).toBeDefined();
      expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Jami darslar")).toBeDefined();
      expect(screen.getByText("10")).toBeDefined();
      expect(screen.getByText("90%")).toBeDefined();
    });

    it("opens teacher profile modal when row is clicked in TeacherGroupStudentsView", async () => {
      vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
        if (url.includes("/api/v1/teacher/groups/grp-1/students")) {
          return Promise.resolve([teacherStudent]);
        }
        if (url.includes("/api/v1/teacher/students/std-100")) {
          return Promise.resolve(teacherStudent);
        }
        return Promise.resolve([teacherStudent]);
      });

      render(<TeacherGroupStudentsView group={teacherGroup} onBack={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getAllByText("Sanjar Qodirov").length).toBeGreaterThanOrEqual(1);
      });

      // Click student row button
      const studentBtn = screen.getByRole("button", { name: /Sanjar Qodirov/i });
      fireEvent.click(studentBtn);

      await waitFor(() => {
        expect(screen.getByRole("dialog")).toBeDefined();
        expect(screen.getByText(/Sanjar Qodirov bo‘yicha batafsil profil/i)).toBeDefined();
      });
    });
  });
});
