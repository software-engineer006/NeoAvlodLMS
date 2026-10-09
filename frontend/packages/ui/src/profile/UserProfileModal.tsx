import React, { useState, useEffect, useRef } from "react";
import type { CurrentUser, PortalType } from "../api/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Modal } from "../components/Modal";
import { Input } from "../components/Input";
import { Button } from "../components/Button";
import { Badge } from "../components/Badge";
import { Alert } from "../components/Alert";
import { NeoAvlodLogo } from "../components/NeoAvlodLogo";
import { PasswordRecoveryModal } from "../auth/PasswordRecoveryModal";
import {
  User,
  Camera,
  Trash2,
  Lock,
  KeyRound,
  CheckCircle2,
  AlertTriangle,
  Send,
} from "lucide-react";

export interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  portal: PortalType;
  user: CurrentUser;
  onUserUpdated: (user: CurrentUser) => void;
  onLogoutRequired: () => void;
}

export const UserProfileModal: React.FC<UserProfileModalProps> = ({
  isOpen,
  onClose,
  portal,
  user,
  onUserUpdated,
  onLogoutRequired,
}) => {
  const [activeTab, setActiveTab] = useState<"profile" | "password">("profile");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Profile form state
  const [firstName, setFirstName] = useState<string>("");
  const [lastName, setLastName] = useState<string>("");
  const [phone, setPhone] = useState<string>("");
  const [username, setUsername] = useState<string>("");
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isSavingProfile, setIsSavingProfile] = useState<boolean>(false);

  // Avatar state
  const [isAvatarLoading, setIsAvatarLoading] = useState<boolean>(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);

  // Password change state
  const [oldPassword, setOldPassword] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [passwordSuccess, setPasswordSuccess] = useState<boolean>(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [isChangingPassword, setIsChangingPassword] = useState<boolean>(false);

  // Password recovery modal state (forgot password via telegram OTP)
  const [isRecoveryOpen, setIsRecoveryOpen] = useState<boolean>(false);

  // Populate form with current user on open
  useEffect(() => {
    if (isOpen && user) {
      setFirstName(user.first_name);
      setLastName(user.last_name ?? "");
      setPhone(user.phone ?? "");
      setUsername(user.username);
      setProfileSuccess(null);
      setProfileError(null);
      setAvatarError(null);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordSuccess(false);
      setPasswordError(null);
      if (user.must_change_password) {
        setActiveTab("password");
      } else {
        setActiveTab("profile");
      }
    }
  }, [isOpen, user]);

  // Handle profile save
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileError(null);
    setProfileSuccess(null);

    if (!firstName.trim()) {
      setProfileError("Ism va familiya to‘ldirilishi shart");
      return;
    }
    if (phone.trim() && !/^\+[1-9][0-9]{7,14}$/.test(phone)) {
      setProfileError("Telefon formati noto‘g‘ri (+998901234567 kabi bo‘lsin)");
      return;
    }
    if (!/^[a-z0-9_]{3,64}$/.test(username.toLowerCase())) {
      setProfileError("Foydalanuvchi nomi kamida 3 belgi, kichik lotin harflari va raqamlardan iborat bo‘lsin");
      return;
    }

    setIsSavingProfile(true);
    try {
      const updated = await apiClient.patch<CurrentUser>(`/api/v1/auth/${portal}/me`, {
        first_name: firstName.trim(),
        last_name: lastName.trim() || undefined,
        phone: phone.trim() || undefined,
        username: username.trim().toLowerCase(),
      });
      onUserUpdated(updated);
      setProfileSuccess("Profil ma’lumotlari muvaffaqiyatli saqlandi");
    } catch (err) {
      if (err instanceof ApiError) {
        setProfileError(err.detail);
      } else {
        setProfileError("Profilni saqlashda kutilmagan xatolik yuz berdi");
      }
    } finally {
      setIsSavingProfile(false);
    }
  };

  // Handle avatar upload
  const handleAvatarFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset input
    e.target.value = "";
    setAvatarError(null);

    // Validate type
    const validTypes = ["image/png", "image/jpeg", "image/webp"];
    if (!validTypes.includes(file.type)) {
      setAvatarError("Faqat PNG, JPEG yoki WebP formatdagi rasmlar qabul qilinadi");
      return;
    }

    // Validate size (5 MB max)
    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
      setAvatarError("Fayl hajmi 5 MB dan oshmasligi kerak");
      return;
    }

    setIsAvatarLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const updated = await apiClient.post<CurrentUser>(
        `/api/v1/auth/${portal}/avatar`,
        formData
      );
      onUserUpdated(updated);
    } catch (err) {
      if (err instanceof ApiError) {
        setAvatarError(err.detail);
      } else {
        setAvatarError("Rasmni yuklashda xatolik yuz berdi");
      }
    } finally {
      setIsAvatarLoading(false);
    }
  };

  // Handle avatar delete
  const handleDeleteAvatar = async () => {
    if (!user.avatar_url) return;
    setIsAvatarLoading(true);
    setAvatarError(null);
    try {
      const updated = await apiClient.delete<CurrentUser>(`/api/v1/auth/${portal}/avatar`);
      onUserUpdated(updated);
    } catch (err) {
      if (err instanceof ApiError) {
        setAvatarError(err.detail);
      } else {
        setAvatarError("Rasmni o‘chirishda xatolik yuz berdi");
      }
    } finally {
      setIsAvatarLoading(false);
    }
  };

  // Handle password change
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);

    if (!oldPassword) {
      setPasswordError("Joriy parolingizni kiriting");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError("Yangi parol kamida 8 ta belgidan iborat bo‘lishi kerak");
      return;
    }
    if (!/[A-Z]/.test(newPassword) || !/[a-z]/.test(newPassword) || !/[0-9]/.test(newPassword)) {
      setPasswordError("Parolda kamida bitta katta harf, bitta kichik harf va bitta raqam bo‘lishi kerak");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Yangi parollar bir-biriga mos kelmadi");
      return;
    }

    setIsChangingPassword(true);
    try {
      await apiClient.post(`/api/v1/auth/${portal}/password/change`, {
        old_password: oldPassword,
        new_password: newPassword,
      });
      setPasswordSuccess(true);
      // Wait 2.5 seconds to show feedback, then log out
      setTimeout(() => {
        onLogoutRequired();
      }, 2500);
    } catch (err) {
      if (err instanceof ApiError) {
        setPasswordError(err.detail);
      } else {
        setPasswordError("Parolni o‘zgartirishda xatolik. Joriy parol noto‘g‘ri bo‘lishi mumkin.");
      }
    } finally {
      setIsChangingPassword(false);
    }
  };

  const initials = `${user.first_name[0] || ""}${user.last_name?.[0] || ""}`.toUpperCase();

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={
          <span className="flex items-center gap-2">
            <NeoAvlodLogo portal={portal} variant="badge" size="xs" />
            <span>Shaxsiy profil</span>
          </span>
        }
        description="Foydalanuvchi ma’lumotlari, profil rasmi va xavfsizlik sozlamalari"
        size="lg"
      >
        {/* Temporary password warning if must_change_password */}
        {user.must_change_password && (
          <div className="mb-4 p-3 bg-amber-50 border border-amber-300 rounded-xl flex items-start gap-3 text-amber-900">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-xs">
              <strong className="block font-semibold">Parolni yangilash talab etiladi:</strong>
              Sizga vaqtinchalik parol berilgan. Xavfsizlik maqsadida iltimos, parolingizni yangilang.
            </div>
          </div>
        )}

        {/* Tab selection */}
        <div className="flex border-b border-slate-200 mb-6">
          <button
            type="button"
            onClick={() => setActiveTab("profile")}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "profile"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <User className="w-4 h-4" />
            Profil ma’lumotlari
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("password")}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "password"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <KeyRound className="w-4 h-4" />
            Xavfsizlik va parol
            {user.must_change_password && (
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping ml-1" />
            )}
          </button>
        </div>

        {/* TAB 1: PROFILE & AVATAR */}
        {activeTab === "profile" && (
          <div className="space-y-6">
            {profileError && (
              <Alert variant="danger" onDismiss={() => setProfileError(null)}>
                {profileError}
              </Alert>
            )}
            {profileSuccess && (
              <Alert variant="success" onDismiss={() => setProfileSuccess(null)}>
                {profileSuccess}
              </Alert>
            )}
            {avatarError && (
              <Alert variant="danger" onDismiss={() => setAvatarError(null)}>
                {avatarError}
              </Alert>
            )}

            {/* Avatar section */}
            <div className="flex flex-col sm:flex-row items-center gap-5 p-4 bg-slate-50 rounded-xl border border-slate-200">
              <div className="relative group shrink-0">
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={`${user.first_name} ${user.last_name ?? ""}`}
                    className="w-20 h-20 rounded-full object-cover border-2 border-white shadow-md ring-2 ring-slate-200"
                  />
                ) : (
                  <div className="w-20 h-20 rounded-full bg-slate-800 text-white flex items-center justify-center font-bold text-2xl shadow-md border-2 border-white ring-2 ring-slate-200">
                    {initials}
                  </div>
                )}
                {isAvatarLoading && (
                  <div className="absolute inset-0 bg-slate-900/60 rounded-full flex items-center justify-center text-white text-xs">
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  </div>
                )}
              </div>

              <div className="space-y-2 text-center sm:text-left flex-1">
                <h4 className="text-sm font-semibold text-slate-900">Profil rasmi</h4>
                <p className="text-xs text-slate-500">
                  PNG, JPEG yoki WebP formatida, maksimal hajmi 5 MB.
                </p>
                <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2 pt-1">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    className="hidden"
                    onChange={handleAvatarFileChange}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={isAvatarLoading}
                    onClick={() => fileInputRef.current?.click()}
                    leftIcon={<Camera className="w-3.5 h-3.5" />}
                  >
                    {user.avatar_url ? "Almashtirish" : "Rasm yuklash"}
                  </Button>
                  {user.avatar_url && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={isAvatarLoading}
                      onClick={handleDeleteAvatar}
                      className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                      leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                    >
                      O‘chirish
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {/* Profile fields form */}
            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Ism"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                  disabled={isSavingProfile}
                />
                <Input
                  label="Familiya"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                                    disabled={isSavingProfile}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Foydalanuvchi nomi (login)"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  disabled={isSavingProfile}
                  helperText="Kichik harflar, raqamlar va pastki chiziq"
                />
                <Input
                  label="Telefon raqami"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                                    disabled={isSavingProfile}
                  placeholder="+998901234567"
                />
              </div>

              {/* Readonly info badges */}
              <div className="p-3 bg-slate-100 rounded-lg flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">Rol:</span>
                  <Badge variant={user.role === "superadmin" ? "danger" : user.role === "admin" ? "info" : "success"}>
                    {user.role === "superadmin" ? "Superadmin" : user.role === "admin" ? "Admin" : "O‘qituvchi"}
                  </Badge>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">Holat:</span>
                  <Badge variant={user.status === "active" ? "success" : "danger"}>
                    {user.status === "active" ? "Faol" : "Nofaol"}
                  </Badge>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">Telegram:</span>
                  <Badge variant={user.telegram_id ? "success" : "neutral"}>
                    {user.telegram_id ? "Ulangan" : "Ulanmagan"}
                  </Badge>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200">
                <Button type="button" variant="outline" onClick={onClose} disabled={isSavingProfile}>
                  Yopish
                </Button>
                <Button type="submit" variant="primary" isLoading={isSavingProfile}>
                  Saqlash
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* TAB 2: PASSWORD CHANGE & RESET */}
        {activeTab === "password" && (
          <div className="space-y-6">
            {passwordSuccess ? (
              <div className="text-center py-6 space-y-4">
                <div className="w-14 h-14 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <h4 className="text-lg font-bold text-slate-900">Parol muvaffaqiyatli yangilandi!</h4>
                <p className="text-sm text-slate-600 max-w-md mx-auto">
                  Xavfsizlik maqsadida barcha faol sessiyalaringiz yakunlandi.
                  Tizim yangi parol bilan qayta kirish uchun login oynasiga yo‘naltirilmoqda...
                </p>
                <div className="flex justify-center pt-2">
                  <div className="w-6 h-6 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
                </div>
              </div>
            ) : (
              <>
                {passwordError && (
                  <Alert variant="danger" onDismiss={() => setPasswordError(null)}>
                    {passwordError}
                  </Alert>
                )}

                <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl text-xs text-blue-900 flex items-start gap-2.5">
                  <Lock className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                  <div>
                    <strong>Xavfsizlik qoidasi:</strong> Yangi parol o‘rnatilgandan so‘ng barcha faol
                    sessiyalar bekor qilinadi va yangi parol bilan tizimga qayta kirish lozim bo‘ladi.
                  </div>
                </div>

                <form onSubmit={handleChangePassword} className="space-y-4">
                  <Input
                    label="Joriy parol"
                    type="password"
                    placeholder="••••••••"
                    required
                    value={oldPassword}
                    onChange={(e) => setOldPassword(e.target.value)}
                    disabled={isChangingPassword}
                  />

                  <Input
                    label="Yangi parol"
                    type="password"
                    placeholder="••••••••"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    disabled={isChangingPassword}
                    helperText="Kamida 8 belgi, bitta katta harf, bitta kichik harf va raqam"
                  />

                  <Input
                    label="Yangi parolni tasdiqlang"
                    type="password"
                    placeholder="••••••••"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    disabled={isChangingPassword}
                  />

                  <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setIsRecoveryOpen(true)}
                      className="text-xs text-blue-600 hover:text-blue-700 font-medium hover:underline flex items-center gap-1"
                    >
                      <Send className="w-3.5 h-3.5" />
                      Joriy parolni unutdingizmi? (Telegram orqali tiklash)
                    </button>

                    <div className="flex items-center gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={onClose}
                        disabled={isChangingPassword}
                      >
                        Bekor qilish
                      </Button>
                      <Button
                        type="submit"
                        variant="primary"
                        isLoading={isChangingPassword}
                      >
                        Parolni yangilash
                      </Button>
                    </div>
                  </div>
                </form>
              </>
            )}
          </div>
        )}
      </Modal>

      {/* Telegram OTP Password Recovery Modal */}
      <PasswordRecoveryModal
        isOpen={isRecoveryOpen}
        onClose={() => setIsRecoveryOpen(false)}
        portal={portal}
        onSuccess={() => {
          setIsRecoveryOpen(false);
          onLogoutRequired();
        }}
      />
    </>
  );
};
