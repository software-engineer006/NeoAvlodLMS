import React, { useState, useEffect } from "react";
import type { CurrentUser, PortalType } from "../api/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Alert } from "../components/Alert";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/Card";
import { Shield, KeyRound, ArrowLeft, Send } from "lucide-react";

export interface LoginFormProps {
  portal: PortalType;
  onSuccess: (user: CurrentUser) => void;
  onForgotPassword?: () => void;
  className?: string;
  localDemo?: boolean;
}

interface LoginChallenge {
  challenge_id: string;
  expires_at: string;
}

export const LoginForm: React.FC<LoginFormProps> = ({
  portal,
  onSuccess,
  onForgotPassword,
  className = "",
  localDemo = false,
}) => {
  // Step 1: Credentials, Step 2: Telegram OTP
  const [step, setStep] = useState<"credentials" | "otp">("credentials");

  // Step 1 fields
  const [username, setUsername] = useState<string>("");
  const [password, setPassword] = useState<string>("");

  // Step 2 fields
  const [challenge, setChallenge] = useState<LoginChallenge | null>(null);
  const [otpCode, setOtpCode] = useState<string>("");
  const [localCode, setLocalCode] = useState<string>("");
  const [secondsRemaining, setSecondsRemaining] = useState<number>(300);

  // States
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Countdown timer for OTP expiration
  useEffect(() => {
    if (step !== "otp" || !challenge) {
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

  const handleCredentialsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("Foydalanuvchi nomi va parolni kiriting");
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.post<LoginChallenge>(`/api/v1/auth/${portal}/login`, {
        username: username.trim(),
        password,
      });
      setChallenge(res);
      setStep("otp");
      setOtpCode("");
      setLocalCode("");
      if (localDemo) {
        const demo = await apiClient.get<{ code: string }>(`/api/v1/local-demo/${portal}/otp/${res.challenge_id}`);
        setLocalCode(demo.code);
      }
      const initialSeconds = Math.max(0, Math.floor((new Date(res.expires_at).getTime() - Date.now()) / 1000));
      setSecondsRemaining(initialSeconds > 0 ? initialSeconds : 300);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Tizimga kirishda xatolik yuz berdi. Iltimos qaytadan urinib ko‘ring.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleOtpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!challenge) {
      return;
    }
    if (secondsRemaining <= 0) {
      setError("Tasdiqlash kodi muddati tugadi. Iltimos, qaytadan kiring.");
      return;
    }
    if (!/^[0-9]{6}$/.test(otpCode)) {
      setError("6 xonali tasdiqlash kodini to‘liq kiriting");
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const user = await apiClient.post<CurrentUser>(`/api/v1/auth/${portal}/login/confirm`, {
        challenge_id: challenge.challenge_id,
        code: otpCode,
      });
      onSuccess(user);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Tasdiqlash kodi noto‘g‘ri yoki muddati tugagan.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const resetToCredentials = () => {
    setStep("credentials");
    setChallenge(null);
    setOtpCode("");
    setLocalCode("");
    setError(null);
  };

  const formatTimer = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainder = secs % 60;
    return `${mins.toString().padStart(2, "0")}:${remainder.toString().padStart(2, "0")}`;
  };

  return (
    <Card className={`w-full max-w-md mx-auto shadow-md ${className}`}>
      <CardHeader className="text-center pb-2">
        <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center mx-auto mb-3">
          {step === "credentials" ? <Shield className="w-6 h-6" /> : <KeyRound className="w-6 h-6" />}
        </div>
        <CardTitle className="text-xl">
          {portal === "admin" ? "Admin tizimiga kirish" : "O‘qituvchi tizimiga kirish"}
        </CardTitle>
        <CardDescription>
          {step === "credentials"
            ? "Hisobingizga kirish uchun ma’lumotlarni kiriting"
            : localDemo
              ? "Quyida ko‘rsatilgan local sinov kodini kiriting"
              : "Telegram botingizga yuborilgan 6 xonali tasdiqlash kodini kiriting"}
        </CardDescription>
      </CardHeader>

      <CardContent>
        {localDemo && (
          <Alert variant="info" className="mb-4">
            Local sinov: login <strong>{portal === "admin" ? "superadmin" : "teacher"}</strong>.
            {localCode && <> Tasdiqlash kodi: <strong>{localCode}</strong></>}
          </Alert>
        )}
        {error && (
          <Alert variant="danger" className="mb-4" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        )}

        {step === "credentials" ? (
          <form onSubmit={handleCredentialsSubmit} className="space-y-4">
            <Input
              label="Foydalanuvchi nomi"
              placeholder="masalan: superowner"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isLoading}
            />

            <Input
              label="Parol"
              type="password"
              placeholder="••••••••"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
            />

            <div className="flex items-center justify-end">
              {onForgotPassword && (
                <button
                  type="button"
                  onClick={onForgotPassword}
                  className="text-xs font-medium text-blue-600 hover:text-blue-800 transition-colors focus:outline-none focus:underline"
                >
                  Parolni unutdingizmi?
                </button>
              )}
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full mt-2"
              isLoading={isLoading}
              rightIcon={<Send className="w-4 h-4" />}
            >
              Kirish
            </Button>
          </form>
        ) : (
          <form onSubmit={handleOtpSubmit} className="space-y-4">
            <div>
              <Input
                label="Tasdiqlash kodi"
                placeholder="123456"
                maxLength={6}
                inputMode="numeric"
                pattern="[0-9]*"
                autoComplete="one-time-code"
                required
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                disabled={isLoading || secondsRemaining <= 0}
                className="text-center tracking-widest text-lg font-mono"
              />
              <div className="flex items-center justify-between mt-2 text-xs text-slate-500">
                <span>Kod amal qilish muddati:</span>
                <span
                  className={`font-mono font-semibold ${
                    secondsRemaining <= 60 ? "text-red-600" : "text-slate-700"
                  }`}
                >
                  {formatTimer(secondsRemaining)}
                </span>
              </div>
            </div>

            {secondsRemaining <= 0 && (
              <Alert variant="warning">
                Tasdiqlash kodi muddati tugadi. Iltimos, qaytadan urinib ko‘ring.
              </Alert>
            )}

            <div className="space-y-2 pt-2">
              <Button
                type="submit"
                variant="primary"
                className="w-full"
                isLoading={isLoading}
                disabled={secondsRemaining <= 0 || otpCode.length !== 6}
              >
                Tasdiqlash
              </Button>

              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={resetToCredentials}
                disabled={isLoading}
                leftIcon={<ArrowLeft className="w-4 h-4" />}
              >
                Orqaga qaytish
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
};
