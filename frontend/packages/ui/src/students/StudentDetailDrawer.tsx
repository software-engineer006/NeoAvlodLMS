import React, { useState, useEffect, useCallback } from "react";
import type { CurrentUser } from "../api/types";
import type { StudentDetailItem } from "./types";
import type { TelegramLinkState } from "../staff/types";
import { hasPermission, PERMISSIONS } from "../navigation/permissions";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Drawer } from "../components/Drawer";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { LoadingState } from "../components/LoadingState";
import { Modal } from "../components/Modal";
import {
  Users,
  Layers,
  Phone,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  RotateCcw,
  ArrowRightLeft,
  Edit2,
  Trash2,
  Send,
} from "lucide-react";

export interface StudentDetailDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  studentId: string | null;
  currentUser: CurrentUser;
  onEdit: (student: StudentDetailItem) => void;
  onTransfer: (student: StudentDetailItem) => void;
  onStatusChanged: () => void;
  onDeleted: () => void;
}

export const StudentDetailDrawer: React.FC<StudentDetailDrawerProps> = ({
  isOpen,
  onClose,
  studentId,
  currentUser,
  onEdit,
  onTransfer,
  onStatusChanged,
  onDeleted,
}) => {
  const canEdit = hasPermission(currentUser, PERMISSIONS.STUDENTS_EDIT);

  const [detail, setDetail] = useState<StudentDetailItem | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Copy states
  const [copiedStudentLink, setCopiedStudentLink] = useState<boolean>(false);
  const [copiedParentLink, setCopiedParentLink] = useState<boolean>(false);

  // Rotating states
  const [isRotatingStudent, setIsRotatingStudent] = useState<boolean>(false);
  const [isRotatingParent, setIsRotatingParent] = useState<boolean>(false);

  // Delete & status toggle states
  const [isTogglingStatus, setIsTogglingStatus] = useState<boolean>(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const loadDetail = useCallback(async () => {
    if (!studentId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<StudentDetailItem>(`/api/v1/admin/students/${studentId}`);
      setDetail(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Talaba ma’lumotlarini yuklashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  }, [studentId]);

  useEffect(() => {
    if (isOpen && studentId) {
      loadDetail();
    } else {
      setDetail(null);
    }
  }, [isOpen, studentId, loadDetail]);

  const handleCopyLink = (link: string, type: "student" | "parent") => {
    navigator.clipboard.writeText(link);
    if (type === "student") {
      setCopiedStudentLink(true);
      setTimeout(() => setCopiedStudentLink(false), 2000);
    } else {
      setCopiedParentLink(true);
      setTimeout(() => setCopiedParentLink(false), 2000);
    }
  };

  const handleRotateStudentLink = async () => {
    if (!detail) return;
    setIsRotatingStudent(true);
    try {
      const newLink = await apiClient.post<TelegramLinkState>(
        `/api/v1/admin/students/${detail.id}/telegram-link`
      );
      setDetail((prev) => (prev ? { ...prev, telegram_link: newLink } : null));
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setIsRotatingStudent(false);
    }
  };

  const handleRotateParentLink = async () => {
    if (!detail) return;
    setIsRotatingParent(true);
    try {
      const newLink = await apiClient.post<TelegramLinkState>(
        `/api/v1/admin/students/${detail.id}/parent/telegram-link`
      );
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              parent: { ...prev.parent, telegram_link: newLink },
            }
          : null
      );
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setIsRotatingParent(false);
    }
  };

  const handleToggleStatus = async () => {
    if (!detail) return;
    setIsTogglingStatus(true);
    try {
      if (detail.status === "active") {
        await apiClient.post(`/api/v1/admin/students/${detail.id}/deactivate`);
      } else {
        await apiClient.post(`/api/v1/admin/students/${detail.id}/activate`);
      }
      await loadDetail();
      onStatusChanged();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setIsTogglingStatus(false);
    }
  };

  const handleDelete = async () => {
    if (!detail) return;
    setIsDeleting(true);
    try {
      await apiClient.delete(`/api/v1/admin/students/${detail.id}`);
      setIsDeleteDialogOpen(false);
      onClose();
      onDeleted();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <Drawer
        isOpen={isOpen}
        onClose={onClose}
        title={detail ? `${detail.first_name} ${detail.last_name}` : "Talaba ma’lumotlari"}
        description={detail ? `Guruh: ${detail.group.name}` : ""}
        size="lg"
      >
        {isLoading && !detail ? (
          <LoadingState message="Talaba ma’lumotlari yuklanmoqda..." />
        ) : error && !detail ? (
          <Alert variant="danger">{error}</Alert>
        ) : detail ? (
          <div className="space-y-6">
            {error && (
              <Alert variant="danger" onDismiss={() => setError(null)}>
                {error}
              </Alert>
            )}

            {/* Student Profile Card */}
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center font-bold text-sm">
                    {detail.first_name[0]}
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-900 text-sm">
                      {detail.first_name} {detail.last_name}
                    </h3>
                    <p className="text-xs text-slate-500">{detail.age} yoshda</p>
                  </div>
                </div>
                <Badge variant={detail.status === "active" ? "success" : "danger"}>
                  {detail.status === "active" ? "Faol" : "Nofaol"}
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-slate-200">
                <div className="flex items-center gap-1.5 text-slate-600">
                  <Phone className="w-3.5 h-3.5 text-slate-400" />
                  <span className="font-mono">{detail.phone}</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-600">
                  <Layers className="w-3.5 h-3.5 text-slate-400" />
                  <span className="font-medium text-slate-900">{detail.group.name}</span>
                </div>
              </div>
            </div>

            {/* Student Telegram Section */}
            <div className="p-4 border border-slate-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-800 font-semibold text-xs">
                  <Send className="w-4 h-4 text-sky-500" />
                  <span>Talaba Telegram hisobi</span>
                </div>
                {detail.telegram_connected ? (
                  <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Ulangan
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                    <XCircle className="w-3.5 h-3.5 text-slate-400" /> Ulanmagan
                  </span>
                )}
              </div>

              {detail.telegram_link?.deep_link && !detail.telegram_connected && (
                <div className="space-y-2 pt-1">
                  <div className="p-2 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between gap-2">
                    <span className="text-[11px] font-mono text-slate-800 break-all select-all">
                      {detail.telegram_link.deep_link}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleCopyLink(detail.telegram_link!.deep_link, "student")}
                      className="shrink-0 text-xs px-2 py-1"
                      leftIcon={
                        copiedStudentLink ? (
                          <Check className="w-3 h-3 text-emerald-600" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )
                      }
                    >
                      {copiedStudentLink ? "Nusxalandi" : "Nusxalash"}
                    </Button>
                  </div>
                </div>
              )}

              {canEdit && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRotateStudentLink}
                  isLoading={isRotatingStudent}
                  leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                  className="w-full text-xs"
                >
                  Yangi talaba havolasini yaratish
                </Button>
              )}
            </div>

            {/* Parent Section */}
            <div className="p-4 border border-slate-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-800 font-semibold text-xs">
                  <Users className="w-4 h-4 text-indigo-600" />
                  <span>Ota-ona ma’lumotlari</span>
                </div>
                {detail.parent.telegram_connected ? (
                  <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Ulangan
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                    <XCircle className="w-3.5 h-3.5 text-slate-400" /> Ulanmagan
                  </span>
                )}
              </div>

              <div className="p-3 bg-slate-50 rounded-lg space-y-1 text-xs">
                <div className="font-semibold text-slate-900">
                  {detail.parent.first_name} {detail.parent.last_name}
                </div>
                <div className="font-mono text-slate-600">{detail.parent.phone}</div>
              </div>

              {detail.parent.telegram_link?.deep_link && !detail.parent.telegram_connected && (
                <div className="space-y-2 pt-1">
                  <div className="p-2 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between gap-2">
                    <span className="text-[11px] font-mono text-slate-800 break-all select-all">
                      {detail.parent.telegram_link.deep_link}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        handleCopyLink(detail.parent.telegram_link!.deep_link, "parent")
                      }
                      className="shrink-0 text-xs px-2 py-1"
                      leftIcon={
                        copiedParentLink ? (
                          <Check className="w-3 h-3 text-emerald-600" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )
                      }
                    >
                      {copiedParentLink ? "Nusxalandi" : "Nusxalash"}
                    </Button>
                  </div>
                </div>
              )}

              {canEdit && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRotateParentLink}
                  isLoading={isRotatingParent}
                  leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                  className="w-full text-xs"
                >
                  Yangi ota-ona havolasini yaratish
                </Button>
              )}
            </div>

            {/* Actions Panel */}
            {canEdit && (
              <div className="pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => onTransfer(detail)}
                    leftIcon={<ArrowRightLeft className="w-4 h-4" />}
                  >
                    Guruhni ko‘chirish
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onEdit(detail)}
                    leftIcon={<Edit2 className="w-4 h-4" />}
                  >
                    Tahrirlash
                  </Button>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleToggleStatus}
                    isLoading={isTogglingStatus}
                    className={
                      detail.status === "active"
                        ? "text-rose-600 hover:text-rose-700"
                        : "text-emerald-600 hover:text-emerald-700"
                    }
                  >
                    {detail.status === "active" ? "Nofaol qilish" : "Faollashtirish"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsDeleteDialogOpen(true)}
                    className="text-rose-600 hover:bg-rose-50"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </Drawer>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={isDeleteDialogOpen}
        onClose={() => setIsDeleteDialogOpen(false)}
        title="Talabani o‘chirish"
        description={`${detail?.first_name} ${detail?.last_name} talabasini tizimdan o‘chirishni tasdiqlaysizmi?`}
        size="sm"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsDeleteDialogOpen(false)}
              disabled={isDeleting}
            >
              Bekor qilish
            </Button>
            <Button variant="danger" size="sm" onClick={handleDelete} isLoading={isDeleting}>
              O‘chirish
            </Button>
          </div>
        }
      >
        <p className="text-sm text-slate-600">
          Ushbu amal talabani va uning barcha bog‘langan qaydlarini butunlay o‘chirib yuboradi.
        </p>
      </Modal>
    </>
  );
};
