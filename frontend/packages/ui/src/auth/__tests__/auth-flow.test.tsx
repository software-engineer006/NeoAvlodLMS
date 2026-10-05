import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { LoginForm } from "../LoginForm";
import { PasswordRecoveryModal } from "../PasswordRecoveryModal";
import { PasswordChangeModal } from "../PasswordChangeModal";
import { apiClient } from "../../api/client";
import type { CurrentUser } from "../../api/types";

describe("Auth Flows & Security Requirements (Task 027)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  describe("LoginForm Flow", () => {
    it("shows a challenge-bound code only in the explicit local demo", async () => {
      vi.spyOn(apiClient, "post").mockResolvedValue({
        challenge_id: "local-challenge",
        expires_at: new Date(Date.now() + 300000).toISOString(),
      });
      const getSpy = vi.spyOn(apiClient, "get").mockResolvedValue({ code: "765432" });
      render(<LoginForm portal="teacher" localDemo onSuccess={vi.fn()} />);
      fireEvent.change(screen.getByLabelText(/Foydalanuvchi nomi/i), { target: { value: "teacher" } });
      fireEvent.change(screen.getByLabelText(/Parol/i), { target: { value: "1234" } });
      fireEvent.click(screen.getByRole("button", { name: /Kirish/i }));
      expect(await screen.findByText("765432")).not.toBeNull();
      expect(getSpy).toHaveBeenCalledWith("/api/v1/local-demo/teacher/otp/local-challenge");
      expect(screen.getByText(/Quyida ko‘rsatilgan local sinov kodini/i)).not.toBeNull();
      expect(localStorage.length).toBe(0);
    });

    it("completes full username/password -> Telegram OTP login cycle", async () => {
      const onSuccess = vi.fn();

      const postSpy = vi.spyOn(apiClient, "post");
      postSpy.mockImplementation((path: string) => {
        if (path === "/api/v1/auth/admin/login") {
          return Promise.resolve({
            challenge_id: "test-challenge-uuid-1234",
            expires_at: new Date(Date.now() + 300000).toISOString(),
          });
        }
        if (path === "/api/v1/auth/admin/login/confirm") {
          return Promise.resolve<CurrentUser>({
            id: "user-uuid-1",
            username: "superowner",
            first_name: "Asad",
            last_name: "Karimov",
            phone: "+998901112233",
            role: "superadmin",
            status: "active",
            permissions: ["*"],
          });
        }
        return Promise.reject(new Error("Unexpected path"));
      });

      render(<LoginForm portal="admin" onSuccess={onSuccess} />);

      // Step 1: Credentials
      const usernameInput = screen.getByLabelText(/Foydalanuvchi nomi/i);
      const passwordInput = screen.getByLabelText(/Parol/i);

      fireEvent.change(usernameInput, { target: { value: "superowner" } });
      fireEvent.change(passwordInput, { target: { value: "SuperSecret123" } });
      fireEvent.click(screen.getByRole("button", { name: /Kirish/i }));

      // Verify Step 1 called login API
      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("/api/v1/auth/admin/login", {
          username: "superowner",
          password: "SuperSecret123",
        });
      });

      // Step 2: Transitions to OTP screen
      const otpInput = await screen.findByLabelText(/Tasdiqlash kodi/i);
      expect(screen.getByText(/Telegram botingizga yuborilgan/i)).not.toBeNull();

      // Enter 6-digit OTP code
      fireEvent.change(otpInput, { target: { value: "987654" } });
      fireEvent.click(screen.getByRole("button", { name: /Tasdiqlash/i }));

      // Verify Step 2 called confirm API
      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("/api/v1/auth/admin/login/confirm", {
          challenge_id: "test-challenge-uuid-1234",
          code: "987654",
        });
      });

      // Verify onSuccess called with profile
      expect(onSuccess).toHaveBeenCalledWith(
        expect.objectContaining({
          username: "superowner",
          role: "superadmin",
        })
      );

      // Verify STRICT SECURITY REQUIREMENT: No secrets in localStorage
      expect(localStorage.getItem("password")).toBeNull();
      expect(localStorage.getItem("token")).toBeNull();
      expect(localStorage.getItem("access_token")).toBeNull();
      expect(localStorage.length).toBe(0);
      expect(sessionStorage.length).toBe(0);
    });

    it("displays expiration warning UX when OTP code expires", async () => {
      vi.spyOn(apiClient, "post").mockResolvedValue({
        challenge_id: "expired-challenge",
        // Already expired
        expires_at: new Date(Date.now() - 5000).toISOString(),
      });

      render(<LoginForm portal="admin" onSuccess={vi.fn()} />);

      fireEvent.change(screen.getByLabelText(/Foydalanuvchi nomi/i), { target: { value: "teacher1" } });
      fireEvent.change(screen.getByLabelText(/Parol/i), { target: { value: "TeacherPass1" } });
      fireEvent.click(screen.getByRole("button", { name: /Kirish/i }));

      expect(await screen.findByLabelText(/Tasdiqlash kodi/i)).not.toBeNull();

      // Should show expiration notice
      await waitFor(() => {
        expect(screen.getByText(/Tasdiqlash kodi muddati tugadi/i)).not.toBeNull();
      });

      // Submit button is disabled
      const submitBtn = screen.getByRole("button", { name: /Tasdiqlash/i }) as HTMLButtonElement;
      expect(submitBtn.disabled).toBe(true);
    });
  });

  describe("Password Recovery Flow", () => {
    it("completes full recovery cycle via Telegram OTP and new password", async () => {
      const onClose = vi.fn();
      const onSuccess = vi.fn();

      const postSpy = vi.spyOn(apiClient, "post");
      postSpy.mockImplementation((path: string) => {
        if (path === "/api/v1/auth/teacher/password/reset") {
          return Promise.resolve({
            challenge_id: "reset-challenge-uuid-5678",
            expires_at: new Date(Date.now() + 300000).toISOString(),
          });
        }
        if (path === "/api/v1/auth/teacher/password/reset/confirm") {
          return Promise.resolve(undefined);
        }
        return Promise.reject(new Error("Unexpected path"));
      });

      render(
        <PasswordRecoveryModal
          isOpen={true}
          onClose={onClose}
          portal="teacher"
          onSuccess={onSuccess}
        />
      );

      // Step 1: Enter username
      expect(screen.getByLabelText(/Foydalanuvchi nomi/i)).not.toBeNull();
      fireEvent.change(screen.getByLabelText(/Foydalanuvchi nomi/i), {
        target: { value: "javohir_teacher" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Kodni yuborish/i }));

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("/api/v1/auth/teacher/password/reset", {
          username: "javohir_teacher",
        });
      });

      // Step 2: OTP + New Password
      const otpInput = await screen.findByLabelText(/Tasdiqlash kodi/i);
      fireEvent.change(otpInput, { target: { value: "112233" } });
      fireEvent.change(document.getElementById("yangi-parol")!, {
        target: { value: "NewSecurePass2026" },
      });
      fireEvent.change(document.getElementById("yangi-parolni-tasdiqlang")!, {
        target: { value: "NewSecurePass2026" },
      });

      fireEvent.click(screen.getByRole("button", { name: /Parolni yangilash/i }));

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("/api/v1/auth/teacher/password/reset/confirm", {
          challenge_id: "reset-challenge-uuid-5678",
          code: "112233",
          new_password: "NewSecurePass2026",
        });
      });

      // Step 3: Success state
      expect(await screen.findByText(/Parol muvaffaqiyatli yangilandi/i)).not.toBeNull();
      expect(onSuccess).toHaveBeenCalled();

      // Security check: No secrets in localStorage
      expect(localStorage.length).toBe(0);
    });
  });

  describe("Password Change Flow", () => {
    it("submits old password and new password to change endpoint", async () => {
      const onClose = vi.fn();
      const onSuccess = vi.fn();

      const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue(undefined);

      render(
        <PasswordChangeModal
          isOpen={true}
          onClose={onClose}
          portal="admin"
          onSuccess={onSuccess}
        />
      );

      fireEvent.change(screen.getByLabelText(/Joriy parol/i), {
        target: { value: "CurrentPass2026" },
      });
      fireEvent.change(document.getElementById("yangi-parol")!, {
        target: { value: "BrandNewPass2026" },
      });
      fireEvent.change(document.getElementById("yangi-parolni-tasdiqlang")!, {
        target: { value: "BrandNewPass2026" },
      });

      fireEvent.click(screen.getByRole("button", { name: /O‘zgartirish/i }));

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("/api/v1/auth/admin/password/change", {
          old_password: "CurrentPass2026",
          new_password: "BrandNewPass2026",
        });
      });

      expect(await screen.findByText(/Parol muvaffaqiyatli o‘zgartirildi/i)).not.toBeNull();
      expect(onSuccess).toHaveBeenCalled();

      // Security check: No secrets in localStorage
      expect(localStorage.length).toBe(0);
    });
  });
});
