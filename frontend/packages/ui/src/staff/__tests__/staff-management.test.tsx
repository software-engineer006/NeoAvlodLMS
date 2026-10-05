import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { StaffTable } from "../StaffTable";
import { StaffModal } from "../StaffModal";
import { TelegramLinkModal } from "../TelegramLinkModal";
import { StaffManagementView } from "../StaffManagementView";
import type { CurrentUser } from "../../api/types";
import type { StaffItem } from "../types";
import { apiClient } from "../../api/client";

describe("Staff & Permission Management (Task 029)", () => {
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

  const adminUser: CurrentUser = {
    id: "ad-1",
    username: "admin_user",
    first_name: "Bobur",
    last_name: "Aliyev",
    phone: "+998902223344",
    role: "admin",
    status: "active",
    permissions: ["staff.manage"],
  };

  const sampleStaffList: StaffItem[] = [
    {
      id: "staff-1",
      first_name: "Dilshod",
      last_name: "Raximov",
      username: "dilshod_math",
      phone: "+998901234567",
      role: "teacher",
      status: "active",
      permissions: [],
      telegram_connected: true,
      created_at: "2026-03-01T10:00:00Z",
    },
    {
      id: "staff-2",
      first_name: "Sardor",
      last_name: "Qodirov",
      username: "sardor_admin",
      phone: "+998909876543",
      role: "admin",
      status: "inactive",
      permissions: ["students.read"],
      telegram_connected: false,
      created_at: "2026-03-02T11:00:00Z",
    },
    {
      id: "sa-1",
      first_name: "Asad",
      last_name: "Karimov",
      username: "superowner",
      phone: "+998901112233",
      role: "superadmin",
      status: "active",
      permissions: [],
      telegram_connected: true,
      created_at: "2026-01-01T00:00:00Z",
    },
  ];

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  describe("StaffTable Component", () => {
    it("renders staff list correctly with roles and status badges", () => {
      render(
        <StaffTable
          staffList={sampleStaffList}
          isLoading={false}
          total={3}
          page={1}
          pageSize={10}
          onPageChange={vi.fn()}
          currentUser={superadminUser}
          onEdit={vi.fn()}
          onToggleStatus={vi.fn()}
          onOpenTelegramModal={vi.fn()}
        />
      );

      expect(screen.getByText("Dilshod Raximov")).toBeDefined();
      expect(screen.getByText("@dilshod_math")).toBeDefined();
      expect(screen.getByText("Sardor Qodirov")).toBeDefined();
      expect(screen.getByText("@sardor_admin")).toBeDefined();

      // Roles badges
      expect(screen.getByText("Bosh admin")).toBeDefined();
      expect(screen.getByText("Administrator")).toBeDefined();
      expect(screen.getByText("O‘qituvchi")).toBeDefined();

      // Telegram connection status
      expect(screen.getAllByText("Bog‘langan").length).toBe(2);
      expect(screen.getByText("Bog‘lanmagan")).toBeDefined();
    });

    it("prevents self-deactivation", () => {
      render(
        <StaffTable
          staffList={sampleStaffList}
          isLoading={false}
          total={3}
          page={1}
          pageSize={10}
          onPageChange={vi.fn()}
          currentUser={superadminUser}
          onEdit={vi.fn()}
          onToggleStatus={vi.fn()}
          onOpenTelegramModal={vi.fn()}
        />
      );

      // Superadmin cannot deactivate themselves (sa-1)
      const deactivateButtons = screen.getAllByTitle(/Faollashtirish|Nofaol qilish/);
      // Total staff = 3, but sa-1 cannot be deactivated, so only 2 status action buttons
      expect(deactivateButtons.length).toBe(2);
    });

    it("allows triggering edit, status toggle, and telegram modal", () => {
      const onEdit = vi.fn();
      const onToggleStatus = vi.fn();
      const onOpenTelegram = vi.fn();

      render(
        <StaffTable
          staffList={sampleStaffList}
          isLoading={false}
          total={3}
          page={1}
          pageSize={10}
          onPageChange={vi.fn()}
          currentUser={superadminUser}
          onEdit={onEdit}
          onToggleStatus={onToggleStatus}
          onOpenTelegramModal={onOpenTelegram}
        />
      );

      const editButtons = screen.getAllByTitle("Tahrirlash");
      fireEvent.click(editButtons[0]);
      expect(onEdit).toHaveBeenCalledWith(sampleStaffList[0]);

      const toggleButtons = screen.getAllByTitle(/Faollashtirish|Nofaol qilish/);
      fireEvent.click(toggleButtons[0]);
      expect(onToggleStatus).toHaveBeenCalledWith(sampleStaffList[0]);

      const telegramButtons = screen.getAllByTitle("Telegram onboarding havolasi");
      fireEvent.click(telegramButtons[0]);
      expect(onOpenTelegram).toHaveBeenCalledWith(sampleStaffList[0]);
    });
  });

  describe("StaffModal Component", () => {
    it("renders create form and performs client validation on invalid phone", async () => {
      render(
        <StaffModal
          isOpen={true}
          onClose={vi.fn()}
          staff={null}
          currentUser={adminUser}
          onSuccess={vi.fn()}
        />
      );

      expect(screen.getByText("Yangi xodim qo‘shish")).toBeDefined();

      const firstNameInput = screen.getByLabelText(/Ism/);
      const lastNameInput = screen.getByLabelText(/Familiya/);
      const phoneInput = screen.getByLabelText(/Telefon raqami/);
      const usernameInput = screen.getByLabelText(/Foydalanuvchi nomi/);
      const passwordInput = screen.getByLabelText(/Boshlang‘ich parol/);

      fireEvent.change(firstNameInput, { target: { value: "Test" } });
      fireEvent.change(lastNameInput, { target: { value: "User" } });
      fireEvent.change(phoneInput, { target: { value: "invalid-phone" } });
      fireEvent.change(usernameInput, { target: { value: "testuser" } });
      fireEvent.change(passwordInput, { target: { value: "pass1234" } });

      const submitBtn = screen.getByRole("button", { name: "Yaratish" });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Telefon raqami formati noto‘g‘ri/)).toBeDefined();
      });
    });

    it("allows superadmin to select role and assign permissions", async () => {
      render(
        <StaffModal
          isOpen={true}
          onClose={vi.fn()}
          staff={null}
          currentUser={superadminUser}
          onSuccess={vi.fn()}
        />
      );

      const roleSelect = screen.getByLabelText(/Xodim roli/);
      fireEvent.change(roleSelect, { target: { value: "admin" } });

      await waitFor(() => {
        expect(screen.getByText("Admin ruxsatlari")).toBeDefined();
        expect(screen.getByText("Xodimlarni boshqarish")).toBeDefined();
        expect(screen.getByText("Fanlarni boshqarish")).toBeDefined();
      });
    });

    it("submits valid create payload to apiClient.post", async () => {
      const postSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce({
        id: "new-staff-id",
        first_name: "Aziz",
        last_name: "Karimov",
        phone: "+998901234567",
        username: "aziz_teacher",
        role: "teacher",
        status: "active",
        permissions: [],
        telegram_connected: false,
        created_at: "2026-03-05T00:00:00Z",
      });

      const onSuccess = vi.fn();
      const onClose = vi.fn();

      render(
        <StaffModal
          isOpen={true}
          onClose={onClose}
          staff={null}
          currentUser={adminUser}
          onSuccess={onSuccess}
        />
      );

      fireEvent.change(screen.getByLabelText(/Ism/), { target: { value: "Aziz" } });
      fireEvent.change(screen.getByLabelText(/Familiya/), { target: { value: "Karimov" } });
      fireEvent.change(screen.getByLabelText(/Telefon raqami/), { target: { value: "+998901234567" } });
      fireEvent.change(screen.getByLabelText(/Foydalanuvchi nomi/), { target: { value: "aziz_teacher" } });
      fireEvent.change(screen.getByLabelText(/Boshlang‘ich parol/), { target: { value: "Secret1234" } });

      fireEvent.click(screen.getByRole("button", { name: "Yaratish" }));

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("/api/v1/admin/staff", {
          first_name: "Aziz",
          last_name: "Karimov",
          phone: "+998901234567",
          username: "aziz_teacher",
          password: "Secret1234",
          role: "teacher",
          permissions: [],
        });
        expect(onSuccess).toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
      });
    });
  });

  describe("TelegramLinkModal Component", () => {
    it("displays telegram deep link and allows copying and rotating", async () => {
      const rotateSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce({
        deep_link: "https://t.me/neoavlod_bot?start=new_token_123",
        expires_at: "2026-03-05T12:00:00Z",
        is_expired: false,
      });

      const linkState = {
        deep_link: "https://t.me/neoavlod_bot?start=old_token_000",
        expires_at: "2026-03-05T10:00:00Z",
        is_expired: false,
      };

      render(
        <TelegramLinkModal
          isOpen={true}
          onClose={vi.fn()}
          staff={sampleStaffList[0]}
          linkState={linkState}
        />
      );

      expect(screen.getByText("Telegram onboarding havolasi")).toBeDefined();
      expect(screen.getByText("https://t.me/neoavlod_bot?start=old_token_000")).toBeDefined();

      const rotateBtn = screen.getByRole("button", { name: "Yangi havola yaratish" });
      fireEvent.click(rotateBtn);

      await waitFor(() => {
        expect(rotateSpy).toHaveBeenCalledWith(`/api/v1/admin/staff/${sampleStaffList[0].id}/telegram-link`);
        expect(screen.getByText("https://t.me/neoavlod_bot?start=new_token_123")).toBeDefined();
      });
    });
  });

  describe("StaffManagementView Integration", () => {
    it("fetches and renders staff list, handles status toggling and guarantees no credentials in localStorage", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue({
        items: sampleStaffList,
        total: 3,
        page: 1,
        page_size: 10,
      });

      const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue({
        id: "staff-1",
        first_name: "Dilshod",
        last_name: "Raximov",
        username: "dilshod_math",
        phone: "+998901234567",
        role: "teacher",
        status: "inactive",
        permissions: [],
        telegram_connected: true,
        created_at: "2026-03-01T10:00:00Z",
      });

      render(<StaffManagementView currentUser={superadminUser} />);

      await waitFor(() => {
        expect(screen.getByText("Xodimlar boshqaruvi")).toBeDefined();
        expect(screen.getByText("Dilshod Raximov")).toBeDefined();
      });

      // Status deactivate action
      const deactivateBtn = screen.getByTitle("Nofaol qilish");
      fireEvent.click(deactivateBtn);

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith(`/api/v1/admin/staff/${sampleStaffList[0].id}/deactivate`);
      });

      // Strict security verification: zero credentials in localStorage or sessionStorage
      expect(localStorage.length).toBe(0);
      expect(sessionStorage.length).toBe(0);
    });
  });
});
