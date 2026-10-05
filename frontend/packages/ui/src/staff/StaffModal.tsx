import React, { useState, useEffect } from "react";
import type { CurrentUser } from "../api/types";
import type { StaffItem, StaffCreateInput, StaffUpdateInput } from "./types";
import { PERMISSIONS } from "../navigation/permissions";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Modal } from "../components/Modal";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";

export interface StaffModalProps {
  isOpen: boolean;
  onClose: () => void;
  staff: StaffItem | null; // null for create, object for edit
  currentUser: CurrentUser;
  onSuccess: (savedStaff: StaffItem) => void;
}

const AVAILABLE_PERMISSIONS = [
  { key: PERMISSIONS.STAFF_MANAGE, label: "Xodimlarni boshqarish" },
  { key: PERMISSIONS.SUBJECTS_MANAGE, label: "Fanlarni boshqarish" },
  { key: PERMISSIONS.GROUPS_READ, label: "Guruhlarni ko‘rish" },
  { key: PERMISSIONS.GROUPS_CREATE, label: "Guruh yaratish" },
  { key: PERMISSIONS.GROUPS_EDIT, label: "Guruhlarni tahrirlash" },
  { key: PERMISSIONS.STUDENTS_READ, label: "Talabalarni ko‘rish" },
  { key: PERMISSIONS.STUDENTS_CREATE, label: "Talaba yaratish" },
  { key: PERMISSIONS.STUDENTS_EDIT, label: "Talabalarni tahrirlash" },
  { key: PERMISSIONS.ATTENDANCE_READ, label: "Davomat tarixini ko‘rish" },
];

export const StaffModal: React.FC<StaffModalProps> = ({
  isOpen,
  onClose,
  staff,
  currentUser,
  onSuccess,
}) => {
  const isEditing = Boolean(staff);
  const isSuperadmin = currentUser.role === "superadmin";

  const [firstName, setFirstName] = useState<string>("");
  const [lastName, setLastName] = useState<string>("");
  const [phone, setPhone] = useState<string>("");
  const [username, setUsername] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [role, setRole] = useState<"admin" | "teacher">("teacher");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (staff) {
      setFirstName(staff.first_name);
      setLastName(staff.last_name);
      setPhone(staff.phone);
      setUsername(staff.username);
      setPassword("");
      setRole(staff.role === "admin" ? "admin" : "teacher");
      setSelectedPermissions(staff.permissions || []);
    } else {
      setFirstName("");
      setLastName("");
      setPhone("+998");
      setUsername("");
      setPassword("");
      setRole("teacher");
      setSelectedPermissions([]);
    }
    setError(null);
  }, [staff, isOpen]);

  const togglePermission = (permKey: string) => {
    setSelectedPermissions((prev) =>
      prev.includes(permKey) ? prev.filter((p) => p !== permKey) : [...prev, permKey]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!firstName.trim() || !lastName.trim()) {
      setError("Ism va familiyani kiriting");
      return;
    }
    if (!/^\+[1-9][0-9]{7,14}$/.test(phone)) {
      setError("Telefon raqami formati noto‘g‘ri (masalan: +998901234567)");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      if (isEditing && staff) {
        const payload: StaffUpdateInput = {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          phone: phone.trim(),
          permissions: isSuperadmin && role === "admin" ? selectedPermissions : undefined,
        };
        const updated = await apiClient.patch<StaffItem>(`/api/v1/admin/staff/${staff.id}`, payload);
        onSuccess(updated);
      } else {
        if (!username.trim() || !password) {
          setError("Foydalanuvchi nomi va parolni kiriting");
          setIsLoading(false);
          return;
        }
        const payload: StaffCreateInput = {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          phone: phone.trim(),
          username: username.trim().toLowerCase(),
          password,
          role: isSuperadmin ? role : "teacher",
          permissions: isSuperadmin && role === "admin" ? selectedPermissions : [],
        };
        const created = await apiClient.post<StaffItem>("/api/v1/admin/staff", payload);
        onSuccess(created);
      }
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Xodimni saqlashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditing ? "Xodim ma’lumotlarini tahrirlash" : "Yangi xodim qo‘shish"}
      description={
        isEditing
          ? `@${staff?.username} ma’lumotlarini yangilash`
          : "Yangi o‘qituvchi yoki administrator hisobini yaratish"
      }
      size="lg"
    >
      {error && (
        <Alert variant="danger" className="mb-4" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Ism"
            placeholder="masalan: Alisher"
            required
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            disabled={isLoading}
          />
          <Input
            label="Familiya"
            placeholder="masalan: Navoiy"
            required
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            disabled={isLoading}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Telefon raqami"
            placeholder="+998901234567"
            required
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            disabled={isLoading}
            helperText="Xalqaro formatda (+998...)"
          />
          {!isEditing && (
            <Input
              label="Foydalanuvchi nomi (Login)"
              placeholder="masalan: alisher_teacher"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isLoading}
              helperText="Kichik lotin harflari va raqamlar"
            />
          )}
        </div>

        {!isEditing && (
          <Input
            label="Boshlang‘ich parol"
            type="password"
            placeholder="••••••••"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isLoading}
            helperText="Kamida 8 belgi, harf va raqam"
          />
        )}

        {/* Role selection (Superadmin only) */}
        {isSuperadmin && !isEditing && (
          <Select
            label="Xodim roli"
            value={role}
            onChange={(e) => setRole(e.target.value as "admin" | "teacher")}
            disabled={isLoading}
            options={[
              { value: "teacher", label: "O‘qituvchi" },
              { value: "admin", label: "Administrator" },
            ]}
          />
        )}

        {/* Permissions selection (Superadmin managing Admin) */}
        {isSuperadmin && role === "admin" && (
          <div className="space-y-2 pt-2 border-t border-slate-100">
            <label className="block text-sm font-medium text-slate-700">
              Admin ruxsatlari
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 bg-slate-50 p-3 rounded-lg border border-slate-200">
              {AVAILABLE_PERMISSIONS.map((perm) => (
                <label key={perm.key} className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedPermissions.includes(perm.key)}
                    onChange={() => togglePermission(perm.key)}
                    disabled={isLoading}
                    className="rounded-sm border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span>{perm.label}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
          <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
            Bekor qilish
          </Button>
          <Button type="submit" variant="primary" isLoading={isLoading}>
            {isEditing ? "Saqlash" : "Yaratish"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
