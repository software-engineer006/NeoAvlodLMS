import React, { useState, useEffect } from "react";
import type { PortalType } from "../api/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Modal } from "../components/Modal";
import { Input } from "../components/Input";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { CheckCircle2, ArrowLeft } from "lucide-react";

export interface PasswordRecoveryModalProps {
  isOpen: boolean;
  onClose: () => void;
  portal: PortalType;
  onSuccess?: () => void;
}

interface ResetChallenge {
  challenge_id: string;
  expires_at: string;
}

export const PasswordRecoveryModal: React.FC<PasswordRecoveryModalProps> = ({
  isOpen,
  onClose,
  portal,
  onSuccess,
}) => {
  const [step, setStep] = useState<"username" | "confirm" | "success">("username");
  const [username, setUsername] = useState<string>("");
  const [challenge, setChallenge] = useState<ResetChallenge | null>(null);
  const [otpCode, setOtpCode] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [secondsRemaining, setSecondsRemaining] = useState<number>(300);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Reset modal state on open/close
  useEffect(() => {
    if (!isOpen) {
      setStep("username");
      setUsername("");
      setChallenge(null);
      setOtpCode("");
      setNewPassword("");
      setConfirmPassword("");
      setError(null);
    }
  }, [isOpen]);

  // Countdown timer for reset OTP
  useEffect(() => {
    if (step !== "confirm" || !challenge) {
      return;
    }
    const expiresAtMs = new Date(challenge.expires_at).getTime();

    const interval = setInterval(() => {
      const remaining = Math.max(0, Math.floor((expiresAtMs - Date.now()) / 1000));
      setSecondsRemaining(remaining);
      if (remaining <= 0) {
        clearInterval(interval);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [step, challenge]);

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) {
      setError("Foydalanuvchi nomini kiriting");
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.post<ResetChallenge>(`/api/v1/auth/${portal}/password/reset`, {
        username: username.trim(),
      });
      setChallenge(res);
      setStep("confirm");
      const initialSeconds = Math.max(0, Math.floor((new Date(res.expires_at).getTime() - Date.now()) / 1000));
      setSecondsRemaining(initialSeconds > 0 ? initialSeconds : 300);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("So‘rov yuborishda xatolik yuz berdi. Iltimos qaytadan urinib ko‘ring.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!challenge) {
      return;
    }
    if (!/^[0-9]{6}$/.test(otpCode)) {
      setError("6 xonali tasdiqlash kodini to‘liq kiriting");
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
      setError("Yangi parollar bir-biriga mos kelmadi");
      return;
    }
    if (secondsRemaining <= 0) {
      setError("Tasdiqlash kodi muddati tugagan. Qaytadan so‘rov yuboring.");
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      await apiClient.post(`/api/v1/auth/${portal}/password/reset/confirm`, {
        challenge_id: challenge.challenge_id,
        code: otpCode,
        new_password: newPassword,
      });
      setStep("success");
      if (onSuccess) {
        onSuccess();
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Parolni yangilashda xatolik yuz berdi. Kod noto‘g‘ri yoki muddati tugagan.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const formatTimer = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainder = secs % 60;
    return `${mins.toString().padStart(2, "0")}:${remainder.toString().padStart(2, "0")}`;
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Parolni tiklash"
      description={
        step === "username"
          ? "Telegram orqali tasdiqlash kodini olish uchun loginni kiriting"
          : step === "confirm"
          ? "Telegramga kelgan kod va yangi parolni kiriting"
          : "Parol muvaffaqiyatli tiklandi"
      }
      size="md"
    >
      {error && (
        <Alert variant="danger" className="mb-4" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {step === "username" && (
        <form onSubmit={handleRequestReset} className="space-y-4">
          <Input
            label="Foydalanuvchi nomi"
            placeholder="masalan: javohir_teacher"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={isLoading}
            helperText="Telegram hisobingizga 6 xonali tasdiqlash kodi yuboriladi"
          />

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
              Bekor qilish
            </Button>
            <Button type="submit" variant="primary" isLoading={isLoading}>
              Kodni yuborish
            </Button>
          </div>
        </form>
      )}

      {step === "confirm" && (
        <form onSubmit={handleConfirmReset} className="space-y-4">
          <div>
            <Input
              label="Tasdiqlash kodi"
              placeholder="123456"
              maxLength={6}
              inputMode="numeric"
              pattern="[0-9]*"
              required
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
              disabled={isLoading || secondsRemaining <= 0}
              className="text-center tracking-widest text-lg font-mono"
            />
            <div className="flex items-center justify-between mt-1 text-xs text-slate-500">
              <span>Amal qilish muddati:</span>
              <span
                className={`font-mono font-semibold ${
                  secondsRemaining <= 60 ? "text-red-600" : "text-slate-700"
                }`}
              >
                {formatTimer(secondsRemaining)}
              </span>
            </div>
          </div>

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

          <div className="flex items-center justify-between gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setStep("username")}
              disabled={isLoading}
              leftIcon={<ArrowLeft className="w-4 h-4" />}
            >
              Orqaga
            </Button>
            <Button
              type="submit"
              variant="primary"
              isLoading={isLoading}
              disabled={secondsRemaining <= 0}
            >
              Parolni yangilash
            </Button>
          </div>
        </form>
      )}

      {step === "success" && (
        <div className="text-center py-4 space-y-4">
          <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <h4 className="text-base font-semibold text-slate-900">Parol muvaffaqiyatli yangilandi</h4>
            <p className="text-sm text-slate-600 mt-1">
              Endi yangi parolingiz bilan tizimga kirishingiz mumkin.
            </p>
          </div>
          <Button variant="primary" onClick={onClose} className="w-full">
            Kirish oynasiga qaytish
          </Button>
        </div>
      )}
    </Modal>
  );
};
