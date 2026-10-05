import React, { useState, useEffect } from "react";
import type { PortalType } from "../api/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Modal } from "../components/Modal";
import { Input } from "../components/Input";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { CheckCircle2 } from "lucide-react";

export interface PasswordChangeModalProps {
  isOpen: boolean;
  onClose: () => void;
  portal: PortalType;
  onSuccess?: () => void;
}

export const PasswordChangeModal: React.FC<PasswordChangeModalProps> = ({
  isOpen,
  onClose,
  portal,
  onSuccess,
}) => {
  const [oldPassword, setOldPassword] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [isSuccess, setIsSuccess] = useState<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setIsSuccess(false);
      setError(null);
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!oldPassword) {
      setError("Joriy parolingizni kiriting");
      return;
    }
    if (newPassword.length < 8) {
      setError("Yangi parol kamida 8 ta belgidan iborat bo‘lishi kerak");
      return;
    }
    if (!/[A-Z]/.test(newPassword) || !/[a-z]/.test(newPassword) || !/[0-9]/.test(newPassword)) {
      setError("Parolda kamida bitta katta harf, bitta kichik harf va bitta raqam bo‘lishi kerak");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Yangi parollar mos kelmadi");
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      await apiClient.post(`/api/v1/auth/${portal}/password/change`, {
        old_password: oldPassword,
        new_password: newPassword,
      });
      setIsSuccess(true);
      if (onSuccess) {
        onSuccess();
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Parolni o‘zgartirishda xatolik yuz berdi. Joriy parol noto‘g‘ri bo‘lishi mumkin.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Parolni o‘zgartirish"
      description="Xavfsizlik maqsadida yangi parol o‘rnatilgach, barcha faol sessiyalar yakunlanadi"
      size="md"
    >
      {error && (
        <Alert variant="danger" className="mb-4" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {isSuccess ? (
        <div className="text-center py-4 space-y-4">
          <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <h4 className="text-base font-semibold text-slate-900">Parol muvaffaqiyatli o‘zgartirildi</h4>
            <p className="text-sm text-slate-600 mt-1">
              Barcha faol sessiyalar bekor qilindi. Yangi parol bilan qaytadan tizimga kiring.
            </p>
          </div>
          <Button variant="primary" onClick={onClose} className="w-full">
            Tushundim
          </Button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Joriy parol"
            type="password"
            placeholder="••••••••"
            required
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            disabled={isLoading}
          />

          <Input
            label="Yangi parol"
            type="password"
            placeholder="••••••••"
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            disabled={isLoading}
            helperText="Kamida 8 belgi, katta-kichik harf va raqam"
          />

          <Input
            label="Yangi parolni tasdiqlang"
            type="password"
            placeholder="••••••••"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={isLoading}
          />

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
              Bekor qilish
            </Button>
            <Button type="submit" variant="primary" isLoading={isLoading}>
              O‘zgartirish
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
};
