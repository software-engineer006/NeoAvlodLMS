import React, { useState } from "react";
import type { StaffItem, TelegramLinkState } from "./types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Modal } from "../components/Modal";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { Send, Copy, Check, RotateCcw } from "lucide-react";

export interface TelegramLinkModalProps {
  isOpen: boolean;
  onClose: () => void;
  staff: StaffItem | null;
  linkState: TelegramLinkState | null;
  onLinkUpdated?: (newLink: TelegramLinkState) => void;
}

export const TelegramLinkModal: React.FC<TelegramLinkModalProps> = ({
  isOpen,
  onClose,
  staff,
  linkState,
  onLinkUpdated,
}) => {
  const [currentLink, setCurrentLink] = useState<TelegramLinkState | null>(linkState);
  const [copied, setCopied] = useState<boolean>(false);
  const [isRotating, setIsRotating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    setCurrentLink(linkState);
    setCopied(false);
    setError(null);
  }, [linkState, isOpen]);

  if (!staff) {
    return null;
  }

  const handleCopy = () => {
    if (!currentLink?.deep_link) return;
    navigator.clipboard.writeText(currentLink.deep_link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRotate = async () => {
    setIsRotating(true);
    setError(null);
    try {
      const updated = await apiClient.post<TelegramLinkState>(
        `/api/v1/admin/staff/${staff.id}/telegram-link`
      );
      setCurrentLink(updated);
      if (onLinkUpdated) {
        onLinkUpdated(updated);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Telegram havolasini yangilashda xatolik yuz berdi");
      }
    } finally {
      setIsRotating(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Telegram onboarding havolasi"
      description={`${staff.first_name} ${staff.last_name} (@${staff.username}) uchun bot havolasi`}
      size="md"
    >
      <div className="space-y-4">
        {error && (
          <Alert variant="danger" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        )}

        {staff.telegram_connected ? (
          <Alert variant="success" title="Hisob bog‘langan">
            Xodim allaqachon Telegram hisobini bog‘lagan. Agar boshqa Telegram hisobiga qayta ulamoqchi bo‘lsangiz, havolani qayta yangilashingiz mumkin.
          </Alert>
        ) : (
          <p className="text-sm text-slate-600">
            Ushbu havolani xodimga yuboring. Xodim havolani ochib Telegram botda <code>/start</code> tugmasini bossa, hisobi tizimga avtomatik bog‘lanadi.
          </p>
        )}

        {currentLink ? (
          <div className="space-y-3">
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between gap-2">
              <span className="text-xs font-mono text-slate-800 break-all select-all">
                {currentLink.deep_link}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopy}
                className="shrink-0"
                leftIcon={copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
              >
                {copied ? "Nusxalandi" : "Nusxalash"}
              </Button>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Amal qilish muddati:</span>
              <span className={currentLink.is_expired ? "text-rose-600 font-semibold" : "font-medium"}>
                {new Date(currentLink.expires_at).toLocaleString("uz-UZ")}
                {currentLink.is_expired && " (Muddati tugagan)"}
              </span>
            </div>
          </div>
        ) : (
          <Alert variant="warning">
            Hozircha Telegram havolasi mavjud emas yoki muddati tugagan.
          </Alert>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-slate-100">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRotate}
            isLoading={isRotating}
            leftIcon={<RotateCcw className="w-4 h-4" />}
          >
            Yangi havola yaratish
          </Button>

          <Button variant="primary" size="sm" onClick={onClose} rightIcon={<Send className="w-4 h-4" />}>
            Tayyor
          </Button>
        </div>
      </div>
    </Modal>
  );
};
