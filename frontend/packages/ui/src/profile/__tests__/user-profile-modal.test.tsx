import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { UserProfileModal } from "../UserProfileModal";
import { AdminShell } from "../../navigation/AdminShell";
import { TeacherShell } from "../../teacher/TeacherShell";
import { apiClient } from "../../api/client";
import type { CurrentUser } from "../../api/types";

describe("User Profile & Password Management UI (Task 051)", () => {
  const mockUser: CurrentUser = {
    id: "user-1",
    username: "dilshod_admin",
    first_name: "Dilshod",
    last_name: "Nazarov",
    phone: "+998901234567",
    role: "admin",
    status: "active",
    permissions: ["staff:manage"],
    telegram_id: 12345678,
    must_change_password: false,
    avatar_url: null,
  };

  const mockTeacher: CurrentUser = {
    id: "user-2",
    username: "muallim_nodir",
    first_name: "Nodir",
    last_name: "Qodirov",
    phone: "+998909876543",
    role: "teacher",
    status: "active",
    permissions: [],
    telegram_id: null,
    must_change_password: true,
    avatar_url: "/media/avatars/avatar_123.png",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders profile details and metadata correctly", () => {
    render(
      <UserProfileModal
        isOpen={true}
        onClose={vi.fn()}
        portal="admin"
        user={mockUser}
        onUserUpdated={vi.fn()}
        onLogoutRequired={vi.fn()}
      />
    );

    expect(screen.getByText("Shaxsiy profil")).toBeDefined();
    expect(screen.getByDisplayValue("Dilshod")).toBeDefined();
    expect(screen.getByDisplayValue("Nazarov")).toBeDefined();
    expect(screen.getByDisplayValue("+998901234567")).toBeDefined();
    expect(screen.getByDisplayValue("dilshod_admin")).toBeDefined();
    expect(screen.getByText("Admin")).toBeDefined();
    expect(screen.getByText("Faol")).toBeDefined();
    expect(screen.getByText("Ulangan")).toBeDefined();
    expect(screen.getByText("DN")).toBeDefined(); // Initials fallback
  });

  it("handles profile update successfully", async () => {
    const handleUpdated = vi.fn();
    const patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValueOnce({
      ...mockUser,
      first_name: "Dilshodbek",
      last_name: "Nazarov",
    });

    render(
      <UserProfileModal
        isOpen={true}
        onClose={vi.fn()}
        portal="admin"
        user={mockUser}
        onUserUpdated={handleUpdated}
        onLogoutRequired={vi.fn()}
      />
    );

    const firstNameInput = screen.getByDisplayValue("Dilshod");
    fireEvent.change(firstNameInput, { target: { value: "Dilshodbek" } });

    const submitBtn = screen.getByRole("button", { name: "Saqlash" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/api/v1/auth/admin/me", {
        first_name: "Dilshodbek",
        last_name: "Nazarov",
        phone: "+998901234567",
        username: "dilshod_admin",
      });
      expect(handleUpdated).toHaveBeenCalledWith(
        expect.objectContaining({ first_name: "Dilshodbek" })
      );
      expect(screen.getByText("Profil ma’lumotlari muvaffaqiyatli saqlandi")).toBeDefined();
    });
  });

  it("handles avatar upload and deletion", async () => {
    const handleUpdated = vi.fn();
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce({
      ...mockUser,
      avatar_url: "/media/avatars/avatar_new.png",
    });
    const deleteSpy = vi.spyOn(apiClient, "delete").mockResolvedValueOnce({
      ...mockUser,
      avatar_url: null,
    });

    const { rerender } = render(
      <UserProfileModal
        isOpen={true}
        onClose={vi.fn()}
        portal="admin"
        user={mockUser}
        onUserUpdated={handleUpdated}
        onLogoutRequired={vi.fn()}
      />
    );

    // Upload avatar
    const file = new File(["dummy content"], "avatar.png", { type: "image/png" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeDefined();

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        "/api/v1/auth/admin/avatar",
        expect.any(FormData)
      );
      expect(handleUpdated).toHaveBeenCalledWith(
        expect.objectContaining({ avatar_url: "/media/avatars/avatar_new.png" })
      );
    });

    // Rerender with user having avatar
    rerender(
      <UserProfileModal
        isOpen={true}
        onClose={vi.fn()}
        portal="admin"
        user={{ ...mockUser, avatar_url: "/media/avatars/avatar_new.png" }}
        onUserUpdated={handleUpdated}
        onLogoutRequired={vi.fn()}
      />
    );

    // Delete avatar
    const deleteBtn = screen.getByRole("button", { name: "O‘chirish" });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith("/api/v1/auth/admin/avatar");
      expect(handleUpdated).toHaveBeenCalledWith(
        expect.objectContaining({ avatar_url: null })
      );
    });
  });

  it("handles password change with validation and session revoke feedback", async () => {
    const handleLogout = vi.fn();
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce(undefined);

    render(
      <UserProfileModal
        isOpen={true}
        onClose={vi.fn()}
        portal="admin"
        user={mockUser}
        onUserUpdated={vi.fn()}
        onLogoutRequired={handleLogout}
      />
    );

    // Switch to password tab
    const passwordTabBtn = screen.getByRole("button", { name: /Xavfsizlik va parol/ });
    fireEvent.click(passwordTabBtn);

    const oldInput = screen.getByLabelText(/^Joriy parol/i);
    const newInput = screen.getByLabelText(/^Yangi parol\b/i);
    const confirmInput = screen.getByLabelText(/tasdiqlang/i);

    fireEvent.change(oldInput, { target: { value: "OldPass123!" } });
    fireEvent.change(newInput, { target: { value: "NewPass123!" } });
    fireEvent.change(confirmInput, { target: { value: "NewPass123!" } });

    const changeBtn = screen.getByRole("button", { name: "Parolni yangilash" });
    fireEvent.click(changeBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/v1/auth/admin/password/change", {
        old_password: "OldPass123!",
        new_password: "NewPass123!",
      });
      expect(screen.getByText("Parol muvaffaqiyatli yangilandi!")).toBeDefined();
    });
  });

  it("displays temporary password warning when must_change_password is true", () => {
    render(
      <UserProfileModal
        isOpen={true}
        onClose={vi.fn()}
        portal="teacher"
        user={mockTeacher}
        onUserUpdated={vi.fn()}
        onLogoutRequired={vi.fn()}
      />
    );

    expect(screen.getByText(/Parolni yangilash talab etiladi/)).toBeDefined();
    expect(screen.getByText(/Sizga vaqtinchalik parol berilgan/)).toBeDefined();
  });

  it("AdminShell triggers onOpenProfile when clicking user or Profilim", () => {
    const handleOpen = vi.fn();
    render(
      <AdminShell
        user={mockTeacher}
        activeTab="dashboard"
        onTabChange={vi.fn()}
        onLogout={vi.fn()}
        onOpenProfile={handleOpen}
      >
        <div>Content</div>
      </AdminShell>
    );

    const profileBtns = screen.getAllByTitle("Shaxsiy profil va rasm");
    expect(profileBtns.length).toBeGreaterThan(0);
    fireEvent.click(profileBtns[0]);
    expect(handleOpen).toHaveBeenCalled();

    // Check temporary password badge in header
    expect(screen.getByTitle("Vaqtinchalik parol: yangilash lozim")).toBeDefined();
  });

  it("TeacherShell triggers onOpenProfile and renders avatar", () => {
    const handleOpen = vi.fn();
    render(
      <TeacherShell
        user={mockTeacher}
        activeTab="groups"
        onTabChange={vi.fn()}
        onLogout={vi.fn()}
        onOpenProfile={handleOpen}
      >
        <div>Teacher content</div>
      </TeacherShell>
    );

    const profileBtns = screen.getAllByTitle("Shaxsiy profil va rasm");
    expect(profileBtns.length).toBeGreaterThan(0);
    fireEvent.click(profileBtns[0]);
    expect(handleOpen).toHaveBeenCalled();
  });
});
