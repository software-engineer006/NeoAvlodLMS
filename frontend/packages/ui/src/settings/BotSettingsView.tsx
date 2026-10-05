import React, { useState, useEffect, useCallback } from "react";
import type { CurrentUser } from "../api/types";
import type { BotSettingsItem, BotTokenUpdateInput } from "./types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Badge } from "../components/Badge";
import { Alert } from "../components/Alert";
import { Modal } from "../components/Modal";
import { LoadingState } from "../components/LoadingState";
import {
  Bot,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Eye,
  EyeOff,
  ShieldAlert,
  Save,
  Key,
} from "lucide-react";

export interface BotSettingsViewProps {
  currentUser: CurrentUser;
}

export const BotSettingsView: React.FC<BotSettingsViewProps> = ({ currentUser }) => {
  // Strict superadmin-only check (Admin and Teacher are forbidden)
  if (currentUser.role !== "superadmin") {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <Alert variant="danger" title="Ruxsat etilmagan (403 Forbidden)">
          Telegram bot sozlamalarini faqat Bosh administrator (Superadmin) boshqarishi mumkin.
          Sizning hisobingizda ushbu modulga kirish huquqi yo‘q.
        </Alert>
      </div>
    );
  }

  const [settings, setSettings] = useState<BotSettingsItem | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Token update form states
  const [newToken, setNewToken] = useState<string>("");
  const [showToken, setShowToken] = useState<boolean>(false);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState<boolean>(false);
  const [isUpdatingToken, setIsUpdatingToken] = useState<boolean>(false);

  const loadSettings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<BotSettingsItem>("/api/v1/admin/settings/bot");
      setSettings(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Bot sozlamalarini yuklashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleOpenConfirm = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newToken.trim()) {
      setError("Iltimos, bot tokenini kiriting");
      return;
    }
    setError(null);
    setIsConfirmModalOpen(true);
  };

  const handleUpdateToken = async () => {
    setIsUpdatingToken(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const payload: BotTokenUpdateInput = {
        token: newToken.trim(),
      };
      const updated = await apiClient.post<BotSettingsItem>("/api/v1/admin/settings/bot", payload);
      setSettings(updated);
      setNewToken("");
      setShowToken(false);
      setIsConfirmModalOpen(false);
      setSuccessMessage("Bot tokeni muvaffaqiyatli yangilandi va worker qayta yuklanishga yuborildi");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Bot tokenini yangilashda xatolik yuz berdi");
      }
      setIsConfirmModalOpen(false);
    } finally {
      setIsUpdatingToken(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Bot className="w-6 h-6 text-blue-600" />
            Telegram Bot sozlamalari
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            LMS tizimining Telegram boti ulanishi, tokenni maskalash va worker holati
          </p>
        </div>
        <div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadSettings}
            disabled={isLoading}
            leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
          >
            Yangilash
          </Button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <Alert variant="danger" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {successMessage && (
        <Alert variant="success" onDismiss={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {isLoading && !settings ? (
        <LoadingState message="Bot sozlamalari yuklanmoqda..." />
      ) : settings ? (
        <div className="space-y-6">
          {/* Status Overview Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center justify-between">
                <span>Bot va Worker holati</span>
                {settings.configured ? (
                  <Badge variant="success" className="gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Sozlangan
                  </Badge>
                ) : (
                  <Badge variant="danger" className="gap-1">
                    <XCircle className="w-3.5 h-3.5" /> Sozlanmagan
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Hozirgi Telegram bot konfiguratsiyasi va integratsiya parametrlari
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-xs text-slate-500 font-medium">Bot Foydalanuvchi nomi</div>
                  <div className="text-base font-semibold text-slate-900 mt-1 font-mono">
                    {settings.bot_username ? (
                      <span className="text-blue-600">@{settings.bot_username}</span>
                    ) : (
                      <span className="text-slate-400 italic">Mavjud emas</span>
                    )}
                  </div>
                </div>

                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-xs text-slate-500 font-medium">Konfiguratsiya versiyasi</div>
                  <div className="text-base font-semibold text-slate-900 mt-1 font-mono">
                    v{settings.version}{" "}
                    <span className="text-xs text-slate-500 font-normal">
                      (faol: v{settings.active_version})
                    </span>
                  </div>
                </div>

                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-xs text-slate-500 font-medium">Worker sinxronizatsiyasi</div>
                  <div className="mt-1">
                    {settings.reload_in_progress ? (
                      <Badge variant="warning" className="gap-1 animate-pulse">
                        <RefreshCw className="w-3 h-3 animate-spin" /> Qayta yuklanmoqda...
                      </Badge>
                    ) : (
                      <Badge variant="success" className="gap-1">
                        <CheckCircle2 className="w-3 h-3" /> Sinxronlashtirilgan
                      </Badge>
                    )}
                  </div>
                </div>
              </div>

              {settings.last_error && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg space-y-1">
                  <div className="text-xs font-semibold text-rose-800 flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4 text-rose-600" />
                    Oxirgi qayd etilgan ulanish xatoligi:
                  </div>
                  <p className="text-xs font-mono text-rose-700 break-all">{settings.last_error}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Token Management Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Key className="w-5 h-5 text-slate-700" />
                <span>Bot tokenini kiritish va almashtirish</span>
              </CardTitle>
              <CardDescription>
                Telegram @BotFather orqali olingan API token. Token server bazasida AES-256 shifrlangan
                holda saqlanadi va brauzerda hech qachon ochiq ko‘rsatilmaydi (maskalanadi).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {settings.configured && (
                <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between">
                  <span className="text-xs text-slate-600">Joriy saqlangan token holati:</span>
                  <span className="text-xs font-mono font-medium tracking-widest text-slate-800">
                    ••••••••••••••••••••••••••••••••••••••••
                  </span>
                </div>
              )}

              <form onSubmit={handleOpenConfirm} noValidate className="space-y-4">
                <div className="relative">
                  <Input
                    label="Yangi Bot Tokeni"
                    type={showToken ? "text" : "password"}
                    placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz..."
                    required
                    value={newToken}
                    onChange={(e) => setNewToken(e.target.value)}
                    disabled={isUpdatingToken}
                    helperText="BotFather dan olingan to‘liq token stringi"
                    rightAddon={
                      <button
                        type="button"
                        onClick={() => setShowToken(!showToken)}
                        className="text-slate-400 hover:text-slate-600 focus:outline-none"
                        aria-label={showToken ? "Tokenni yashirish" : "Tokenni ko‘rsatish"}
                      >
                        {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    }
                  />
                </div>

                <div className="flex items-center justify-end pt-2">
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={!newToken.trim() || isUpdatingToken}
                    leftIcon={<Save className="w-4 h-4" />}
                  >
                    Tokenni saqlash va yangilash
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* Confirmation Modal */}
      <Modal
        isOpen={isConfirmModalOpen}
        onClose={() => setIsConfirmModalOpen(false)}
        title="Bot tokenini yangilash tasdig‘i"
        description="Ushbu amal barcha Telegram integratsiyalari faoliyatiga ta’sir qiladi"
        size="md"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsConfirmModalOpen(false)}
              disabled={isUpdatingToken}
            >
              Bekor qilish
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleUpdateToken}
              isLoading={isUpdatingToken}
            >
              Tasdiqlash va saqlash
            </Button>
          </div>
        }
      >
        <div className="space-y-3 text-sm text-slate-600">
          <p>
            Yangi token kiritilganda tizim quyidagi amallarni bajaradi:
          </p>
          <ul className="list-disc pl-5 space-y-1 text-xs text-slate-700">
            <li>Telegram API ga so‘rov yuborib, token to‘g‘riligini va bot nomini tekshiradi</li>
            <li>Tokenni shifrlab ma’lumotlar bazasida saqlaydi</li>
            <li>Faol Telegram worker jarayoniga yangi konfiguratsiyani qayta yuklash buyrug‘ini beradi</li>
          </ul>
          <p className="text-xs text-amber-600 font-medium">
            Agar token noto‘g‘ri kiritilsa, bot xabarnomalari to‘xtab qolishi mumkin.
          </p>
        </div>
      </Modal>
    </div>
  );
};
