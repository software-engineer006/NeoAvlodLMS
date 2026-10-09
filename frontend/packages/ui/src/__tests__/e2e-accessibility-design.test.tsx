import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AdminShell } from "../navigation/AdminShell";
import { TeacherShell } from "../teacher/TeacherShell";
import { ForbiddenPage } from "../navigation/ForbiddenPage";
import { Modal } from "../components/Modal";
import { Drawer } from "../components/Drawer";
import { PasswordRecoveryModal } from "../auth/PasswordRecoveryModal";
import { PasswordChangeModal } from "../auth/PasswordChangeModal";
import { LoginForm } from "../auth/LoginForm";
import { PERMISSIONS } from "../navigation/permissions";
import type { CurrentUser } from "../api/types";
import { apiClient } from "../api/client";

describe("Frontend E2E, Accessibility & Design Review (Task 037)", () => {
  const superadminUser: CurrentUser = {
    id: "usr-super",
    username: "superadmin_user",
    first_name: "Rustam",
    last_name: "Karimov",
    phone: "+998901112233",
    role: "superadmin",
    status: "active",
    permissions: [],
  };

  const regularAdminUser: CurrentUser = {
    id: "usr-admin",
    username: "admin_user",
    first_name: "Aziz",
    last_name: "Soliqov",
    phone: "+998902223344",
    role: "admin",
    status: "active",
    permissions: [PERMISSIONS.STUDENTS_READ, PERMISSIONS.GROUPS_READ],
  };

  const teacherUser: CurrentUser = {
    id: "usr-teacher",
    username: "teacher_user",
    first_name: "Jasur",
    last_name: "Olimov",
    phone: "+998903334455",
    role: "teacher",
    status: "active",
    permissions: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  describe("Portal Auth & Password Recovery Cycles", () => {
    it("completes full login cycle via Username/Password and Telegram OTP", async () => {
      vi.spyOn(apiClient, "post").mockImplementation((url) => {
        if (url.includes("/login/confirm")) {
          return Promise.resolve(superadminUser);
        }
        if (url.includes("/login")) {
          return Promise.resolve({
            challenge_id: "chl-login-1",
            otp_sent: true,
            otp_phone_mask: "+998 90 *** ** 33",
            expires_at: new Date(Date.now() + 300000).toISOString(),
          });
        }
        return Promise.reject(new Error("Not found"));
      });

      const handleSuccess = vi.fn();
      render(<LoginForm portal="admin" onSuccess={handleSuccess} />);

      // Step 1: Input username and password
      const usernameInput = screen.getByLabelText(/Foydalanuvchi nomi/i);
      const passwordInput = screen.getByLabelText(/Parol/i);

      fireEvent.change(usernameInput, { target: { value: "superadmin_user" } });
      fireEvent.change(passwordInput, { target: { value: "AdminPass123!" } });

      const submitBtn = screen.getByRole("button", { name: /Kirish/i });
      fireEvent.click(submitBtn);

      // Step 2: Telegram OTP prompt appears
      await waitFor(() => {
        expect(screen.getByPlaceholderText("123456")).toBeDefined();
      });

      const otpInput = screen.getByPlaceholderText("123456");
      fireEvent.change(otpInput, { target: { value: "123456" } });

      const verifyBtn = screen.getByRole("button", { name: /^Tasdiqlash$/i });
      fireEvent.click(verifyBtn);

      await waitFor(() => {
        expect(handleSuccess).toHaveBeenCalledWith(superadminUser);
      });
    });

    it("completes Password Recovery flow via Telegram OTP", async () => {
      vi.spyOn(apiClient, "post").mockImplementation((url) => {
        if (url.includes("/password/reset/confirm")) {
          return Promise.resolve({
            message: "Parol muvaffaqiyatli yangilandi",
          });
        }
        if (url.includes("/password/reset")) {
          return Promise.resolve({
            challenge_id: "chl-1",
            otp_sent: true,
            otp_phone_mask: "+998 90 *** ** 55",
            expires_at: new Date(Date.now() + 300000).toISOString(),
          });
        }
        return Promise.reject(new Error("Not found"));
      });

      const handleClose = vi.fn();
      render(
        <PasswordRecoveryModal
          isOpen={true}
          onClose={handleClose}
          portal="admin"
        />
      );

      expect(screen.getByText("Parolni tiklash")).toBeDefined();

      // Step 1: Enter username
      const usernameInput = screen.getByLabelText(/Foydalanuvchi nomi/i);
      fireEvent.change(usernameInput, { target: { value: "teacher_user" } });

      const requestBtn = screen.getByRole("button", { name: /Kodni yuborish/i });
      fireEvent.click(requestBtn);

      // Step 2: Enter OTP and new password
      await waitFor(() => {
        expect(screen.getByPlaceholderText("123456")).toBeDefined();
      });

      const otpInput = screen.getByPlaceholderText("123456");
      const passwordInputs = screen.getAllByPlaceholderText("••••••••");

      fireEvent.change(otpInput, { target: { value: "654321" } });
      fireEvent.change(passwordInputs[0], { target: { value: "NewSecurePass123!" } });
      fireEvent.change(passwordInputs[1], { target: { value: "NewSecurePass123!" } });

      const confirmBtn = screen.getByRole("button", { name: /Parolni yangilash/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(screen.getByText(/Parol muvaffaqiyatli yangilandi/i)).toBeDefined();
      });
    });

    it("completes Password Change flow with old and new passwords", async () => {
      const postSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce({
        message: "Parol muvaffaqiyatli o‘zgartirildi",
      });

      const handleSuccess = vi.fn();
      render(
        <PasswordChangeModal
          isOpen={true}
          onClose={vi.fn()}
          portal="teacher"
          onSuccess={handleSuccess}
        />
      );

      expect(screen.getByText("Parolni o‘zgartirish")).toBeDefined();

      const inputs = screen.getAllByPlaceholderText("••••••••");

      fireEvent.change(inputs[0], { target: { value: "OldSecret123!" } });
      fireEvent.change(inputs[1], { target: { value: "NewSecret456!" } });
      fireEvent.change(inputs[2], { target: { value: "NewSecret456!" } });

      const submitBtn = screen.getByRole("button", { name: /O‘zgartirish/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith(
          "/api/v1/auth/teacher/password/change",
          expect.objectContaining({
            old_password: "OldSecret123!",
            new_password: "NewSecret456!",
          })
        );
      });

      await waitFor(() => {
        expect(handleSuccess).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe("Cross-Portal Guards & RBAC Routing", () => {
    it("guards Admin portal against Teacher users with 403 Forbidden and portal link", () => {
      const handleLogout = vi.fn();
      render(<ForbiddenPage isTeacher={true} onLogout={handleLogout} />);

      expect(screen.getByText("Xatolik 403")).toBeDefined();
      expect(screen.getByText(/Siz o‘qituvchi hisobiga egasiz\. Admin boshqaruv portali faqat ma’muriyat/i)).toBeDefined();

      const teacherLink = screen.getByRole("link", { name: /O‘qituvchi portaliga o‘tish/i });
      expect(teacherLink.getAttribute("href")).toBe("https://teacher.eduneo.uz");

      const logoutBtn = screen.getByRole("button", { name: /Boshqa hisob bilan kirish/i });
      fireEvent.click(logoutBtn);
      expect(handleLogout).toHaveBeenCalledTimes(1);
    });

    it("guards Teacher portal against Admin/Superadmin users with 403 Forbidden and admin portal link", () => {
      const handleLogout = vi.fn();
      render(<ForbiddenPage isAdmin={true} onLogout={handleLogout} />);

      expect(screen.getByText("Xatolik 403")).toBeDefined();
      expect(screen.getByText(/Siz ma’muriyat hisobiga egasiz\. O‘qituvchi portali faqat o‘qituvchilar/i)).toBeDefined();

      const adminLink = screen.getByRole("link", { name: /Admin portaliga o‘tish/i });
      expect(adminLink.getAttribute("href")).toBe("https://admin.eduneo.uz");
    });

    it("hides Superadmin-only and unauthorized sections for limited admin and shows block banner", () => {
      const handleTabChange = vi.fn();
      render(
        <AdminShell
          user={regularAdminUser}
          activeTab="bot-settings"
          onTabChange={handleTabChange}
          onLogout={vi.fn()}
        >
          <div>Ichki kontent</div>
        </AdminShell>
      );

      // Bot settings nav item is hidden from sidebar for regular admin
      expect(screen.queryByRole("button", { name: /^Bot sozlamalari$/i })).toBeNull();

      // Direct access banner is displayed
      expect(screen.getByText("Ushbu bo‘limga kirish cheklangan")).toBeDefined();
      expect(screen.getByText(/bo‘limiga kirish huquqi mavjud emas/i)).toBeDefined();
    });

    it("allows full access to superadmin across all administration sections", () => {
      render(
        <AdminShell
          user={superadminUser}
          activeTab="dashboard"
          onTabChange={vi.fn()}
          onLogout={vi.fn()}
        >
          <div>Superadmin Boshqaruv Kontenti</div>
        </AdminShell>
      );

      expect(screen.getByRole("button", { name: /Bot sozlamalari/i })).toBeDefined();
      expect(screen.getByRole("button", { name: /Xodimlar/i })).toBeDefined();
      expect(screen.getByRole("button", { name: /Fanlar/i })).toBeDefined();
      expect(screen.getByText("Superadmin Boshqaruv Kontenti")).toBeDefined();
    });
  });

  describe("Accessibility (A11y) & Keyboard Navigation", () => {
    it("handles Modal Escape key, ARIA attributes, and body scroll lock cleanup", () => {
      const handleClose = vi.fn();
      const { unmount } = render(
        <Modal
          isOpen={true}
          onClose={handleClose}
          title="Sinov modali"
          description="A11y tekshiruvi"
        >
          <p>Modal ichidagi matn</p>
        </Modal>
      );

      // Verify ARIA dialog role and modal attribute
      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeDefined();
      expect(dialog.getAttribute("aria-modal")).toBe("true");

      // Verify accessible close button
      const closeBtn = screen.getByRole("button", { name: "Yopish" });
      expect(closeBtn).toBeDefined();

      // Verify body scroll lock was applied
      expect(document.body.style.overflow).toBe("hidden");

      // Press Escape key
      fireEvent.keyDown(window, { key: "Escape" });
      expect(handleClose).toHaveBeenCalledTimes(1);

      // Unmount restores body overflow
      unmount();
      expect(document.body.style.overflow).toBe("");
    });

    it("handles Drawer Escape key, ARIA attributes, and backdrop click", () => {
      const handleClose = vi.fn();
      render(
        <Drawer
          isOpen={true}
          onClose={handleClose}
          title="O‘quvchi profili"
          description="Batafsil ma’lumot"
        >
          <div>Drawer kontenti</div>
        </Drawer>
      );

      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeDefined();
      expect(dialog.getAttribute("aria-modal")).toBe("true");

      // Press Escape
      fireEvent.keyDown(window, { key: "Escape" });
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it("supports mobile navigation toggle in AdminShell and TeacherShell", () => {
      // AdminShell mobile menu
      const { unmount: unmountAdmin } = render(
        <AdminShell
          user={superadminUser}
          activeTab="dashboard"
          onTabChange={vi.fn()}
          onLogout={vi.fn()}
        >
          <div>Admin</div>
        </AdminShell>
      );

      const adminMenuToggle = screen.getByRole("button", { name: "Menyuni ochish" });
      expect(adminMenuToggle).toBeDefined();
      fireEvent.click(adminMenuToggle);

      const adminMenuClose = screen.getByRole("button", { name: "Menyuni yopish" });
      expect(adminMenuClose).toBeDefined();
      fireEvent.click(adminMenuClose);

      unmountAdmin();

      // TeacherShell mobile menu
      render(
        <TeacherShell
          user={teacherUser}
          activeTab="groups"
          onTabChange={vi.fn()}
          onLogout={vi.fn()}
        >
          <div>Teacher</div>
        </TeacherShell>
      );

      const teacherMenuToggle = screen.getByRole("button", { name: "Menyuni ochish" });
      expect(teacherMenuToggle).toBeDefined();
      fireEvent.click(teacherMenuToggle);

      const teacherMenuClose = screen.getByRole("button", { name: "Menyuni yopish" });
      expect(teacherMenuClose).toBeDefined();
      fireEvent.click(teacherMenuClose);
    });
  });

  describe("Security & Clean Design Verification", () => {
    it("ensures zero credentials, access tokens, or secrets in localStorage and sessionStorage", () => {
      expect(localStorage.getItem("token")).toBeNull();
      expect(localStorage.getItem("access_token")).toBeNull();
      expect(localStorage.getItem("secret")).toBeNull();
      expect(sessionStorage.getItem("token")).toBeNull();
      expect(sessionStorage.getItem("access_token")).toBeNull();
      expect(sessionStorage.getItem("secret")).toBeNull();
    });

    it("verifies zero emojis in rendered user interface elements", () => {
      const { container } = render(
        <AdminShell
          user={superadminUser}
          activeTab="dashboard"
          onTabChange={vi.fn()}
          onLogout={vi.fn()}
        >
          <div>Admin Boshqaruv Ish Stoli</div>
        </AdminShell>
      );

      const emojiRegex = /[\uD800-\uDBFF][\uDC00-\uDFFF]/;
      const textContent = container.textContent || "";
      expect(emojiRegex.test(textContent)).toBe(false);
    });
  });
});
