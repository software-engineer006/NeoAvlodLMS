import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AdminShell } from "../AdminShell";
import { ForbiddenPage } from "../ForbiddenPage";
import { hasPermission, canManageBot, PERMISSIONS } from "../permissions";
import type { CurrentUser } from "../../api/types";

describe("Admin Shell & Permission Routing (Task 028)", () => {
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

  const limitedAdminUser: CurrentUser = {
    id: "ad-1",
    username: "student_manager",
    first_name: "Bobur",
    last_name: "Aliyev",
    phone: "+998902223344",
    role: "admin",
    status: "active",
    permissions: [PERMISSIONS.STUDENTS_READ],
  };

  const teacherUser: CurrentUser = {
    id: "tc-1",
    username: "javohir_teacher",
    first_name: "Javohir",
    last_name: "Toshmatov",
    phone: "+998903334455",
    role: "teacher",
    status: "active",
    permissions: [PERMISSIONS.STUDENTS_READ, PERMISSIONS.GROUPS_READ],
  };

  describe("Permission logic unit checks", () => {
    it("superadmin has all permissions and bot management", () => {
      expect(hasPermission(superadminUser, PERMISSIONS.STAFF_MANAGE)).toBe(true);
      expect(hasPermission(superadminUser, PERMISSIONS.SUBJECTS_MANAGE)).toBe(true);
      expect(hasPermission(superadminUser, PERMISSIONS.STUDENTS_READ)).toBe(true);
      expect(canManageBot(superadminUser)).toBe(true);
    });

    it("admin has only explicitly granted permissions and cannot manage bot", () => {
      expect(hasPermission(limitedAdminUser, PERMISSIONS.STUDENTS_READ)).toBe(true);
      expect(hasPermission(limitedAdminUser, PERMISSIONS.STAFF_MANAGE)).toBe(false);
      expect(hasPermission(limitedAdminUser, PERMISSIONS.SUBJECTS_MANAGE)).toBe(false);
      expect(canManageBot(limitedAdminUser)).toBe(false);
    });

    it("teacher has NO admin permissions regardless of permissions array", () => {
      expect(hasPermission(teacherUser, PERMISSIONS.STUDENTS_READ)).toBe(false);
      expect(hasPermission(teacherUser, PERMISSIONS.GROUPS_READ)).toBe(false);
      expect(canManageBot(teacherUser)).toBe(false);
    });
  });

  describe("Teacher 403 Forbidden Page", () => {
    it("renders dedicated 403 page for teacher with portal link and logout", () => {
      const onLogout = vi.fn();
      render(<ForbiddenPage isTeacher={true} onLogout={onLogout} />);

      expect(screen.getByText(/Xatolik 403/i)).not.toBeNull();
      expect(screen.getByText(/Ruxsat berilmagan/i)).not.toBeNull();
      expect(screen.getByText(/Siz o‘qituvchi hisobiga egasiz/i)).not.toBeNull();
      expect(screen.getByRole("link", { name: /O‘qituvchi portaliga o‘tish/i })).not.toBeNull();

      fireEvent.click(screen.getByRole("button", { name: /Chiqish/i }));
      expect(onLogout).toHaveBeenCalled();
    });
  });

  describe("AdminShell Navigation & Visibility", () => {
    it("superadmin sees all navigation items including Bot sozlamalari", () => {
      const onTabChange = vi.fn();
      const onLogout = vi.fn();

      render(
        <AdminShell
          user={superadminUser}
          activeTab="dashboard"
          onTabChange={onTabChange}
          onLogout={onLogout}
        >
          <div>Dashboard Content</div>
        </AdminShell>
      );

      // Verify all navigation items exist for superadmin
      expect(screen.getByRole("button", { name: /Bosh sahifa/i })).not.toBeNull();
      expect(screen.getByRole("button", { name: /Xodimlar/i })).not.toBeNull();
      expect(screen.getByRole("button", { name: /Fanlar/i })).not.toBeNull();
      expect(screen.getByRole("button", { name: /Guruhlar/i })).not.toBeNull();
      expect(screen.getByRole("button", { name: /Talabalar/i })).not.toBeNull();
      expect(screen.getByRole("button", { name: /Davomat tarixi/i })).not.toBeNull();
      expect(screen.getByRole("button", { name: /Bot sozlamalari/i })).not.toBeNull();
    });

    it("limited admin only sees permitted navigation items", () => {
      const onTabChange = vi.fn();
      const onLogout = vi.fn();

      render(
        <AdminShell
          user={limitedAdminUser}
          activeTab="dashboard"
          onTabChange={onTabChange}
          onLogout={onLogout}
        >
          <div>Dashboard Content</div>
        </AdminShell>
      );

      // Should see Dashboard and Talabalar
      expect(screen.getByRole("button", { name: /Bosh sahifa/i })).not.toBeNull();
      expect(screen.getByRole("button", { name: /Talabalar/i })).not.toBeNull();

      // Should NOT see unauthorized items
      expect(screen.queryByRole("button", { name: /Xodimlar/i })).toBeNull();
      expect(screen.queryByRole("button", { name: /Fanlar/i })).toBeNull();
      expect(screen.queryByRole("button", { name: /Guruhlar/i })).toBeNull();
      expect(screen.queryByRole("button", { name: /Bot sozlamalari/i })).toBeNull();
    });

    it("blocks unauthorized tab access and displays warning", () => {
      const onTabChange = vi.fn();
      const onLogout = vi.fn();

      render(
        <AdminShell
          user={limitedAdminUser}
          activeTab="staff" // unauthorized tab
          onTabChange={onTabChange}
          onLogout={onLogout}
        >
          <div>Staff Content (Should not be shown)</div>
        </AdminShell>
      );

      // Content blocked
      expect(screen.queryByText(/Staff Content/i)).toBeNull();
      expect(screen.getByText(/Ushbu bo‘limga kirish cheklangan/i)).not.toBeNull();

      // Return to dashboard button
      fireEvent.click(screen.getByRole("button", { name: /Bosh sahifaga qaytish/i }));
      expect(onTabChange).toHaveBeenCalledWith("dashboard");
    });

    it("triggers logout when logout button in header is clicked", () => {
      const onLogout = vi.fn();
      render(
        <AdminShell
          user={superadminUser}
          activeTab="dashboard"
          onTabChange={vi.fn()}
          onLogout={onLogout}
        >
          <div>Content</div>
        </AdminShell>
      );

      const logoutBtns = screen.getAllByRole("button", { name: /Chiqish/i });
      fireEvent.click(logoutBtns[0]);
      expect(onLogout).toHaveBeenCalled();
    });
  });
});
