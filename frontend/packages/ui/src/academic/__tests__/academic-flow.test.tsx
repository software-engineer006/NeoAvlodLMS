import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { OccupancyBadge } from "../OccupancyBadge";
import { SubjectModal } from "../SubjectModal";
import { SubjectsManagementView } from "../SubjectsManagementView";
import { GroupModal } from "../GroupModal";
import { GroupsManagementView } from "../GroupsManagementView";
import { formatDaysOfWeek, formatPrice } from "../types";
import type { CurrentUser } from "../../api/types";
import type { SubjectItem, GroupItem } from "../types";
import { apiClient } from "../../api/client";
import { PERMISSIONS } from "../../navigation/permissions";

describe("Academic: Subject & Group Management (Task 030)", () => {
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
    username: "reader_admin",
    first_name: "Bobur",
    last_name: "Aliyev",
    phone: "+998902223344",
    role: "admin",
    status: "active",
    permissions: [PERMISSIONS.GROUPS_READ, PERMISSIONS.SUBJECTS_MANAGE],
  };

  const fullAdminUser: CurrentUser = {
    id: "ad-full",
    username: "academic_admin",
    first_name: "Temur",
    last_name: "Sharipov",
    phone: "+998903334455",
    role: "admin",
    status: "active",
    permissions: [
      PERMISSIONS.GROUPS_READ,
      PERMISSIONS.GROUPS_CREATE,
      PERMISSIONS.GROUPS_EDIT,
      PERMISSIONS.SUBJECTS_MANAGE,
    ],
  };

  const sampleSubjects: SubjectItem[] = [
    {
      id: "sub-1",
      name: "Python Backend",
      description: "Python FastAPI va PostgreSQL kursi",
      is_active: true,
      active_groups: 2,
      total_groups: 3,
      created_at: "2026-01-10T10:00:00Z",
    },
    {
      id: "sub-2",
      name: "Frontend React",
      description: "React va TypeScript kursi",
      is_active: false,
      active_groups: 0,
      total_groups: 1,
      created_at: "2026-02-15T12:00:00Z",
    },
  ];

  const sampleGroups: GroupItem[] = [
    {
      id: "grp-1",
      name: "Python Pro - 101",
      subject_id: "sub-1",
      teacher_id: "tch-1",
      monthly_price: "600000.00",
      max_students: 12,
      current_students: 10,
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
      max_students: 15,
      current_students: 15, // 100% full
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

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  describe("Helper formatters", () => {
    it("formats days of week and presets correctly", () => {
      expect(formatDaysOfWeek([1, 3, 5])).toBe("Dush / Chor / Juma");
      expect(formatDaysOfWeek([2, 4, 6])).toBe("Sesh / Pay / Shan");
      expect(formatDaysOfWeek([1, 2, 3, 4, 5, 6])).toBe("Dush-Shan (Har kuni)");
      expect(formatDaysOfWeek([])).toBe("-");
    });

    it("formats monthly price in Uzbek Sum", () => {
      expect(formatPrice("600000.00")).toContain("600");
      expect(formatPrice("600000.00")).toContain("so‘m");
    });
  });

  describe("OccupancyBadge Component", () => {
    it("renders occupancy ratio and percentage", () => {
      render(<OccupancyBadge current={6} max={12} />);
      expect(screen.getByText("6 / 12")).toBeDefined();
      expect(screen.getByText("50%")).toBeDefined();
    });

    it("renders full group capacity indication (100%)", () => {
      render(<OccupancyBadge current={15} max={15} />);
      expect(screen.getByText("15 / 15")).toBeDefined();
      expect(screen.getByText("100%")).toBeDefined();
    });
  });

  describe("SubjectModal Component", () => {
    it("validates empty name before submission", async () => {
      render(
        <SubjectModal
          isOpen={true}
          onClose={vi.fn()}
          subject={null}
          onSuccess={vi.fn()}
        />
      );

      const submitBtn = screen.getByRole("button", { name: "Yaratish" });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText("Fan nomini kiriting")).toBeDefined();
      });
    });

    it("submits valid create payload to apiClient.post", async () => {
      const postSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce({
        id: "new-sub-1",
        name: "Go Backend",
        description: "Golang dasturlash kursi",
        is_active: true,
        active_groups: 0,
        total_groups: 0,
        created_at: "2026-03-01T00:00:00Z",
      });

      const onSuccess = vi.fn();
      const onClose = vi.fn();

      render(
        <SubjectModal
          isOpen={true}
          onClose={onClose}
          subject={null}
          onSuccess={onSuccess}
        />
      );

      fireEvent.change(screen.getByLabelText(/Fan nomi/), { target: { value: "Go Backend" } });
      fireEvent.change(screen.getByLabelText(/Tavsif/), { target: { value: "Golang dasturlash kursi" } });

      fireEvent.click(screen.getByRole("button", { name: "Yaratish" }));

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("/api/v1/admin/subjects", {
          name: "Go Backend",
          description: "Golang dasturlash kursi",
        });
        expect(onSuccess).toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
      });
    });
  });

  describe("SubjectsManagementView", () => {
    it("loads subjects, toggles status and handles delete confirmation", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue({
        items: sampleSubjects,
        total: 2,
        page: 1,
        page_size: 10,
      });

      const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue({
        ...sampleSubjects[0],
        is_active: false,
      });

      const deleteSpy = vi.spyOn(apiClient, "delete").mockResolvedValue({});

      render(<SubjectsManagementView currentUser={superadminUser} />);

      await waitFor(() => {
        expect(screen.getByText("Python Backend")).toBeDefined();
        expect(screen.getByText("Frontend React")).toBeDefined();
      });

      // Toggle status on first subject (active -> deactivate)
      const deactivateBtn = screen.getByTitle("Nofaol qilish");
      fireEvent.click(deactivateBtn);

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith(`/api/v1/admin/subjects/${sampleSubjects[0].id}/deactivate`);
      });

      // Delete action opens confirm modal
      const deleteButtons = screen.getAllByTitle("O‘chirish");
      fireEvent.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByText(/fanini tizimdan o‘chirishni tasdiqlaysizmi/)).toBeDefined();
      });

      // Confirm delete inside modal
      const modal = screen.getByRole("dialog");
      const confirmDeleteBtn = within(modal).getByRole("button", { name: "O‘chirish" });
      fireEvent.click(confirmDeleteBtn);

      await waitFor(() => {
        expect(deleteSpy).toHaveBeenCalledWith(`/api/v1/admin/subjects/${sampleSubjects[0].id}`);
      });
    });
  });

  describe("GroupModal Component", () => {
    it("validates time order when start_time >= end_time", async () => {
      vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
        if (url.includes("/api/v1/admin/subjects")) {
          return Promise.resolve({ items: sampleSubjects });
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
          });
        }
        return Promise.resolve({ items: [] });
      });

      render(
        <GroupModal
          isOpen={true}
          onClose={vi.fn()}
          group={null}
          onSuccess={vi.fn()}
        />
      );

      // Wait for options to load
      await waitFor(() => {
        expect(screen.getByText("Python Backend")).toBeDefined();
      });

      fireEvent.change(screen.getByLabelText(/Guruh nomi/), { target: { value: "Test Group" } });
      fireEvent.change(screen.getByLabelText(/Dars boshlanish vaqti/), { target: { value: "14:00" } });
      fireEvent.change(screen.getByLabelText(/Dars tugash vaqti/), { target: { value: "12:00" } }); // Invalid!
      fireEvent.change(screen.getByLabelText(/Xona raqami/), { target: { value: "101" } });

      fireEvent.click(screen.getByRole("button", { name: "Yaratish" }));

      await waitFor(() => {
        expect(screen.getByText(/Dars boshlanish vaqti tugash vaqtidan oldin bo‘lishi kerak/)).toBeDefined();
      });
    });
  });

  describe("GroupsManagementView & RBAC Permission Handling", () => {
    beforeEach(() => {
      vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
        if (url.includes("/api/v1/admin/subjects")) {
          return Promise.resolve({ items: sampleSubjects, total: 2, page: 1, page_size: 10 });
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
        if (url.includes("/api/v1/admin/groups")) {
          return Promise.resolve({
            items: sampleGroups,
            total: 2,
            page: 1,
            page_size: 10,
          });
        }
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      });
    });

    it("hides create, edit and delete buttons for read-only admin", async () => {
      render(<GroupsManagementView currentUser={readOnlyAdminUser} />);

      await waitFor(() => {
        expect(screen.getByText("Python Pro - 101")).toBeDefined();
      });

      // "Yangi guruh" button should NOT be rendered
      expect(screen.queryByRole("button", { name: /Yangi guruh/ })).toBeNull();

      // Edit and delete action buttons should NOT be rendered
      expect(screen.queryByTitle("Tahrirlash")).toBeNull();
      expect(screen.queryByTitle("O‘chirish")).toBeNull();
    });

    it("renders full CRUD actions for superadmin or authorized admin and ensures zero secrets in localStorage", async () => {
      render(<GroupsManagementView currentUser={fullAdminUser} />);

      await waitFor(() => {
        expect(screen.getByText("Python Pro - 101")).toBeDefined();
        expect(screen.getByRole("button", { name: /Yangi guruh/ })).toBeDefined();
        expect(screen.getAllByTitle("Tahrirlash").length).toBe(2);
      });

      // Strict security assertion: zero secrets in storage
      expect(localStorage.length).toBe(0);
      expect(sessionStorage.length).toBe(0);
    });
  });
});
