import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { StudentModal } from "../StudentModal";
import { StudentTransferModal } from "../StudentTransferModal";
import { StudentDetailDrawer } from "../StudentDetailDrawer";
import { StudentsManagementView } from "../StudentsManagementView";
import type { CurrentUser } from "../../api/types";
import type { StudentItem, StudentDetailItem } from "../types";
import type { GroupItem } from "../../academic/types";
import { PERMISSIONS } from "../../navigation/permissions";
import { apiClient } from "../../api/client";
import { ApiError } from "../../api/errors";

describe("Student & Parent Management (Task 031)", () => {
  const superadminUser: CurrentUser = {
    id: "sa-1",
    username: "superowner",
    first_name: "Asad",
    last_name: "Karimov",
    phone: "+998901112233",
    role: "superadmin",
    status: "active",
    permissions: [],
  };

  const readOnlyAdminUser: CurrentUser = {
    id: "ad-reader",
    username: "student_reader",
    first_name: "Bobur",
    last_name: "Aliyev",
    phone: "+998902223344",
    role: "admin",
    status: "active",
    permissions: [PERMISSIONS.STUDENTS_READ],
  };

  const fullAdminUser: CurrentUser = {
    id: "ad-full",
    username: "student_manager",
    first_name: "Temur",
    last_name: "Sharipov",
    phone: "+998903334455",
    role: "admin",
    status: "active",
    permissions: [
      PERMISSIONS.STUDENTS_READ,
      PERMISSIONS.STUDENTS_CREATE,
      PERMISSIONS.STUDENTS_EDIT,
    ],
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
    {
      id: "grp-2",
      name: "Python Beginners - 102",
      subject_id: "sub-1",
      teacher_id: "tch-1",
      monthly_price: "500000.00",
      max_students: 10,
      current_students: 10, // Full capacity!
      status: "active",
      days_of_week: [2, 4, 6],
      start_time: "14:00:00",
      end_time: "16:00:00",
      room_number: "202-xona",
      created_at: "2026-02-05T10:00:00Z",
      updated_at: "2026-02-05T10:00:00Z",
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

  const sampleStudents: StudentItem[] = [
    {
      id: "st-1",
      first_name: "Jasur",
      last_name: "Bekmurodov",
      phone: "+998901110011",
      age: 16,
      status: "active",
      group_id: "grp-1",
      parent_id: "pr-1",
      telegram_connected: true,
      created_at: "2026-02-10T10:00:00Z",
      parent: {
        id: "pr-1",
        first_name: "Otabek",
        last_name: "Bekmurodov",
        phone: "+998909998877",
        telegram_connected: false,
        created_at: "2026-02-10T10:00:00Z",
      },
      group: {
        id: "grp-1",
        name: "Python Pro - 101",
        status: "active",
      },
    },
    {
      id: "st-2",
      first_name: "Kamola",
      last_name: "Ismoilova",
      phone: "+998902220022",
      age: 17,
      status: "inactive",
      group_id: "grp-1",
      parent_id: "pr-2",
      telegram_connected: false,
      created_at: "2026-02-12T10:00:00Z",
      parent: {
        id: "pr-2",
        first_name: "Gulnora",
        last_name: "Ismoilova",
        phone: "+998908887766",
        telegram_connected: true,
        created_at: "2026-02-12T10:00:00Z",
      },
      group: {
        id: "grp-1",
        name: "Python Pro - 101",
        status: "active",
      },
    },
  ];

  const sampleStudentDetail: StudentDetailItem = {
    ...sampleStudents[0],
    telegram_link: {
      deep_link: "https://t.me/neoavlod_bot?start=st_tok_111",
      expires_at: "2026-03-10T10:00:00Z",
      is_expired: false,
    },
    parent: {
      ...sampleStudents[0].parent!,
      telegram_link: {
        deep_link: "https://t.me/neoavlod_bot?start=pr_tok_222",
        expires_at: "2026-03-10T10:00:00Z",
        is_expired: false,
      },
    },
  };

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  describe("StudentModal Component", () => {
    it("validates invalid student and parent inputs", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue({ items: sampleGroups });

      render(
        <StudentModal
          isOpen={true}
          onClose={vi.fn()}
          student={null}
          onSuccess={vi.fn()}
        />
      );

      // Attempt submit without filling
      fireEvent.click(screen.getByRole("button", { name: "Ro‘yxatga olish" }));

      await waitFor(() => {
        expect(screen.getByText("O‘quvchi ismini kiriting")).toBeDefined();
      });
    });

    it("handles 409 Group Capacity Full error", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue({ items: sampleGroups });
      vi.spyOn(apiClient, "post").mockRejectedValue(
        new ApiError(409, "Guruh to‘lgan: maksimal sig‘imga yetgan (12/12)")
      );

      render(
        <StudentModal
          isOpen={true}
          onClose={vi.fn()}
          student={null}
          onSuccess={vi.fn()}
        />
      );

      // Wait for groups to load
      await waitFor(() => {
        expect(screen.getByText(/Python Pro - 101/)).toBeDefined();
      });

      // Fill student info
      fireEvent.change(screen.getByLabelText(/^Ism\b/), { target: { value: "Anvar" } });
      fireEvent.change(screen.getByLabelText(/^Familiya\b/), { target: { value: "Soliyev" } });
      fireEvent.change(screen.getByLabelText(/^Telefon raqami\b/), { target: { value: "+998901234567" } });
      fireEvent.change(screen.getByLabelText(/Yoshi/), { target: { value: "16" } });

      // Fill parent info
      fireEvent.change(screen.getByLabelText(/Ota-ona ismi/), { target: { value: "Baxrom" } });
      fireEvent.change(screen.getByLabelText(/Ota-ona familiyasi/), { target: { value: "Soliyev" } });
      fireEvent.change(screen.getByLabelText(/Ota-ona telefon raqami/), { target: { value: "+998907654321" } });

      fireEvent.click(screen.getByRole("button", { name: "Ro‘yxatga olish" }));

      await waitFor(() => {
        expect(screen.getByText(/Guruh to‘lgan: maksimal sig‘imga yetgan/)).toBeDefined();
      });
    });

    it("submits unified student + parent payload successfully", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue({ items: sampleGroups });
      const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue(sampleStudentDetail);

      const onSuccess = vi.fn();
      const onClose = vi.fn();

      render(
        <StudentModal
          isOpen={true}
          onClose={onClose}
          student={null}
          onSuccess={onSuccess}
        />
      );

      // Wait for groups to load
      await waitFor(() => {
        expect(screen.getByText(/Python Pro - 101/)).toBeDefined();
      });

      fireEvent.change(screen.getByLabelText(/^Ism\b/), { target: { value: "Anvar" } });
      fireEvent.change(screen.getByLabelText(/^Familiya\b/), { target: { value: "Soliyev" } });
      fireEvent.change(screen.getByLabelText(/^Telefon raqami\b/), { target: { value: "+998901234567" } });
      fireEvent.change(screen.getByLabelText(/Yoshi/), { target: { value: "16" } });

      fireEvent.change(screen.getByLabelText(/Ota-ona ismi/), { target: { value: "Baxrom" } });
      fireEvent.change(screen.getByLabelText(/Ota-ona familiyasi/), { target: { value: "Soliyev" } });
      fireEvent.change(screen.getByLabelText(/Ota-ona telefon raqami/), { target: { value: "+998907654321" } });

      fireEvent.click(screen.getByRole("button", { name: "Ro‘yxatga olish" }));

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("/api/v1/admin/students", {
          first_name: "Anvar",
          last_name: "Soliyev",
          phone: "+998901234567",
          age: 16,
          group_id: "grp-1",
          parent: {
            first_name: "Baxrom",
            last_name: "Soliyev",
            phone: "+998907654321",
          },
        });
        expect(onSuccess).toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
      });
    });
  });

  describe("StudentTransferModal Component", () => {
    it("handles transferring student to another group and displays capacity warnings", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue({ items: sampleGroups });
      const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue(sampleStudentDetail);

      const onSuccess = vi.fn();
      const onClose = vi.fn();

      render(
        <StudentTransferModal
          isOpen={true}
          onClose={onClose}
          student={sampleStudents[0]}
          onSuccess={onSuccess}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Python Beginners - 102/)).toBeDefined();
      });

      // Target group grp-2 is full, so warning alert appears
      expect(screen.getByText(/Tanlangan guruh allaqachon maksimal sig‘imga yetgan/)).toBeDefined();

      fireEvent.click(screen.getByRole("button", { name: "Guruhga ko‘chirish" }));

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith(
          `/api/v1/admin/students/${sampleStudents[0].id}/transfer`,
          { target_group_id: "grp-2" }
        );
        expect(onSuccess).toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
      });
    });
  });

  describe("StudentDetailDrawer Component", () => {
    it("renders drawer with student and parent telegram deep links and rotation actions", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue(sampleStudentDetail);
      const rotateStudentSpy = vi.spyOn(apiClient, "post").mockResolvedValue({
        deep_link: "https://t.me/neoavlod_bot?start=new_st_link",
        expires_at: "2026-03-12T10:00:00Z",
        is_expired: false,
      });

      render(
        <StudentDetailDrawer
          isOpen={true}
          onClose={vi.fn()}
          studentId={sampleStudents[0].id}
          currentUser={fullAdminUser}
          onEdit={vi.fn()}
          onTransfer={vi.fn()}
          onStatusChanged={vi.fn()}
          onDeleted={vi.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getAllByText("Jasur Bekmurodov").length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText("Otabek Bekmurodov")).toBeDefined();
        expect(screen.getByText("https://t.me/neoavlod_bot?start=pr_tok_222")).toBeDefined();
      });

      // Rotate student telegram link
      const rotateStudentBtn = screen.getByRole("button", {
        name: "Yangi o‘quvchi havolasini yaratish",
      });
      fireEvent.click(rotateStudentBtn);

      await waitFor(() => {
        expect(rotateStudentSpy).toHaveBeenCalledWith(
          `/api/v1/admin/students/${sampleStudents[0].id}/telegram-link`
        );
      });
    });
  });

  describe("StudentsManagementView & RBAC Permission Handling", () => {
    beforeEach(() => {
      vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
        if (url.includes("/api/v1/admin/groups")) {
          return Promise.resolve({ items: sampleGroups, total: 2, page: 1, page_size: 10 });
        }
        if (url.includes("/api/v1/admin/students")) {
          return Promise.resolve({
            items: sampleStudents,
            total: 2,
            page: 1,
            page_size: 10,
          });
        }
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      });
    });

    it("hides mutating action buttons for read-only admin", async () => {
      render(<StudentsManagementView currentUser={readOnlyAdminUser} />);

      await waitFor(() => {
        expect(screen.getByText("Jasur Bekmurodov")).toBeDefined();
      });

      // "Yangi o‘quvchi" button should NOT be rendered
      expect(screen.queryByRole("button", { name: /Yangi o‘quvchi/ })).toBeNull();

      // Mutating table actions should NOT be rendered
      expect(screen.queryByTitle("Guruhni ko‘chirish")).toBeNull();
      expect(screen.queryByTitle("Tahrirlash")).toBeNull();

      // Read-only "Batafsil" should be available
      expect(screen.getAllByTitle("Batafsil ma’lumot").length).toBe(2);
    });

    it("renders full CRUD actions for authorized admin and verifies storage security", async () => {
      render(<StudentsManagementView currentUser={fullAdminUser} />);

      await waitFor(() => {
        expect(screen.getByText("Jasur Bekmurodov")).toBeDefined();
        expect(screen.getByRole("button", { name: /Yangi o‘quvchi/ })).toBeDefined();
        expect(screen.getAllByTitle("Guruhni ko‘chirish").length).toBe(2);
        expect(screen.getAllByTitle("Tahrirlash").length).toBe(2);
      });

      // Storage security assertion
      expect(localStorage.length).toBe(0);
      expect(sessionStorage.length).toBe(0);
    });

    it("renders full CRUD actions for superadmin as well", async () => {
      render(<StudentsManagementView currentUser={superadminUser} />);

      await waitFor(() => {
        expect(screen.getByText("Jasur Bekmurodov")).toBeDefined();
        expect(screen.getByRole("button", { name: /Yangi o‘quvchi/ })).toBeDefined();
      });
    });
  });
});
