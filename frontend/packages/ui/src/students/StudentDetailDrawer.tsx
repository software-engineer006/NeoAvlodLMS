import { CalendarInput } from "../components/CalendarInput";
import { formatDate, formatMonth, shiftMonth, tashkentMonth } from "../lib/dates";
import React, { useState, useEffect, useCallback } from "react";
import type { CurrentUser } from "../api/types";
import type { StudentDetailItem } from "./types";
import { studentEnrollments } from "./types";
import { StudentGroupsPanel } from "./StudentGroupsPanel";
import type { TelegramLinkState } from "../staff/types";
import { hasPermission, PERMISSIONS } from "../navigation/permissions";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { LoadingState } from "../components/LoadingState";
import { Modal } from "../components/Modal";
import {
  Users,
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
  Calendar,
  UserCheck,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Percent,
} from "lucide-react";

export interface StudentProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  studentId: string | null;
  currentUser: CurrentUser;
  onEdit?: (student: StudentDetailItem) => void;
  onTransfer?: (student: StudentDetailItem) => void;
  onStatusChanged?: () => void;
  onDeleted?: () => void;
}

export type StudentDetailDrawerProps = StudentProfileModalProps;

const getAdjacentMonth = shiftMonth;

export const StudentProfileModal: React.FC<StudentProfileModalProps> = ({
  isOpen,
  onClose,
  studentId,
  currentUser,
  onEdit,
  onTransfer,
  onStatusChanged,
  onDeleted,
}) => {
  const canEdit = hasPermission(currentUser, PERMISSIONS.STUDENTS_EDIT)
    && !!onEdit && !!onTransfer && !!onStatusChanged && !!onDeleted;
  const canReadAttendance = hasPermission(currentUser, PERMISSIONS.ATTENDANCE_READ);

  const [detail, setDetail] = useState<StudentDetailItem | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isStatsLoading, setIsStatsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedMonth, setSelectedMonth] = useState<string>(() => tashkentMonth());

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

  const loadDetail = useCallback(
    async (monthToFetch?: string, isMonthSwitch = false) => {
      if (!studentId) return;
      if (isMonthSwitch) {
        setIsStatsLoading(true);
      } else {
        setIsLoading(true);
      }
      setError(null);
      try {
        const monthQuery = monthToFetch || selectedMonth;
        const data = await apiClient.get<StudentDetailItem>(
          `/api/v1/admin/students/${studentId}?month=${monthQuery}`
        );
        setDetail(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError("O‘quvchi ma’lumotlarini yuklashda xatolik yuz berdi");
        }
      } finally {
        setIsLoading(false);
        setIsStatsLoading(false);
      }
    },
    [studentId, selectedMonth]
  );

  useEffect(() => {
    if (isOpen && studentId) {
      loadDetail(selectedMonth, false);
    } else {
      setDetail(null);
      setError(null);
    }
  }, [isOpen, studentId]);

  const handleMonthChange = (newMonth: string) => {
    setSelectedMonth(newMonth);
    loadDetail(newMonth, true);
  };

  const handlePrevMonth = () => {
    const prev = getAdjacentMonth(selectedMonth, -1);
    handleMonthChange(prev);
  };

  const handleNextMonth = () => {
    const next = getAdjacentMonth(selectedMonth, 1);
    handleMonthChange(next);
  };

  const handleCopyLink = (link: string | null | undefined, type: "student" | "parent") => {
    if (!link) return;
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
    if (!detail?.parent) return;
    setIsRotatingParent(true);
    try {
      const newLink = await apiClient.post<TelegramLinkState>(
        `/api/v1/admin/students/${detail.id}/parent/telegram-link`
      );
      setDetail((prev) =>
        prev?.parent
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
      await loadDetail(selectedMonth, false);
      onStatusChanged?.();
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
      onDeleted?.();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setIsDeleting(false);
    }
  };

  const formattedCreatedDate = detail?.created_at ? formatDate(detail.created_at) : "—";

  const attendanceStats = detail?.attendance_stats;
  const attendanceRate =
    attendanceStats && attendanceStats.total_lessons > 0
      ? Math.round((attendanceStats.attended_count / attendanceStats.total_lessons) * 100)
      : 0;

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={
          detail ? (
            <div className="flex items-center gap-2">
              <span>{detail.first_name} {detail.last_name}</span>
              <Badge variant={detail.status === "active" ? "success" : "danger"} size="sm">
                {detail.status === "active" ? "Faol" : "Nofaol"}
              </Badge>
            </div>
          ) : (
            "O‘quvchi profili"
          )
        }
        description={detail ? `Guruhlar: ${studentEnrollments(detail).filter((item) => item.is_active).length} • Ro‘yxatga olingan: ${formattedCreatedDate}` : ""}
        size="2xl"
        footer={
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              {canEdit && detail && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onTransfer?.(detail)}
                    leftIcon={<ArrowRightLeft className="w-4 h-4 text-indigo-600" />}
                  >
                    Guruhni ko‘chirish
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onEdit?.(detail)}
                    leftIcon={<Edit2 className="w-4 h-4 text-slate-600" />}
                  >
                    Tahrirlash
                  </Button>
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
                    aria-label="O‘quvchini o‘chirish"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </>
              )}
            </div>
            <Button variant="outline" size="sm" onClick={onClose}>
              Yopish
            </Button>
          </div>
        }
      >
        {isLoading && !detail ? (
          <LoadingState message="O‘quvchi ma’lumotlari yuklanmoqda..." />
        ) : error && !detail ? (
          <Alert variant="danger">{error}</Alert>
        ) : detail ? (
          <div className="space-y-6">
            {error && (
              <Alert variant="danger" onDismiss={() => setError(null)}>
                {error}
              </Alert>
            )}

            {/* 1. Student Profile Card */}
            <div className="p-4 sm:p-5 bg-slate-50 border border-slate-200 rounded-xl space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-lg">
                    {detail.first_name?.[0] || "O"}
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">
                      {detail.first_name} {detail.last_name}
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">{detail.age == null ? (detail.school_grade ?? "Yosh kiritilmagan") : `${detail.age} yoshda`}</p>
                  </div>
                </div>
                <Badge variant={detail.status === "active" ? "success" : "danger"}>
                  {detail.status === "active" ? "Faol" : "Nofaol"}
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-slate-200/80 text-xs">
                <div>
                  <span className="text-slate-500 block mb-0.5 font-medium">Telefon raqami</span>
                  <a
                    href={detail.phone ? `tel:${detail.phone}` : undefined}
                    className="inline-flex items-center gap-1.5 font-mono text-slate-900 font-semibold hover:text-blue-600 transition-colors"
                  >
                    <Phone className="w-3.5 h-3.5 text-slate-400" />
                    <span>{detail.phone ?? "Kiritilmagan"}</span>
                  </a>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5 font-medium">Ro‘yxatga olingan sana</span>
                  <div className="inline-flex items-center gap-1.5 text-slate-700 font-medium">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    <span>{formattedCreatedDate}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Group & Lesson Details */}
            {(detail.school_grade || detail.school_name || detail.import_notes?.length) && (
              <div className="p-4 border border-slate-200 rounded-xl space-y-2 text-sm">
                {detail.school_grade && <p><strong>Sinf:</strong> {detail.school_grade}</p>}
                {detail.school_name && <p><strong>Maktabi:</strong> {detail.school_name}</p>}
                {!!detail.import_notes?.length && <div><strong>Manbadagi izohlar</strong>{detail.import_notes.map((note, index) => <p key={index}>{note}</p>)}</div>}
              </div>
            )}
            <StudentGroupsPanel key={detail.id} student={detail} canEdit={canEdit} onUpdated={(updated) => {
              setDetail((current) => current?.id === updated.id ? { ...updated,
                attendance_stats: updated.attendance_stats ?? current.attendance_stats } : current); onStatusChanged?.();
            }} />

            {/* 3. Parent & Contacts */}
            <div className="p-4 sm:p-5 border border-slate-200 rounded-xl space-y-3 bg-white">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-900 font-semibold text-sm">
                  <Users className="w-4 h-4 text-indigo-600" />
                  <span>Ota-ona ma’lumotlari</span>
                </div>
                {detail.parent?.telegram_connected ? (
                  <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Ulangan
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                    <XCircle className="w-3.5 h-3.5 text-slate-400" /> Ulanmagan
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-1">
                <div className="p-3 bg-slate-50 rounded-lg space-y-1">
                  <span className="text-slate-500 block">F.I.Sh</span>
                  <div className="font-semibold text-slate-900 text-sm">
                    {detail.parent?.first_name ?? "Kiritilmagan"} {detail.parent?.last_name}
                  </div>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg space-y-1">
                  <span className="text-slate-500 block">Aloqa telefoni</span>
                  <a
                    href={detail.parent?.phone ? `tel:${detail.parent.phone}` : undefined}
                    className="font-mono text-slate-900 font-semibold hover:text-indigo-600 transition-colors inline-flex items-center gap-1.5"
                  >
                    <Phone className="w-3.5 h-3.5 text-slate-400" />
                    {detail.parent?.phone ?? "Kiritilmagan"}
                  </a>
                </div>
              </div>
            </div>

            {/* 4. Telegram Integration Section */}
            <div className="p-4 sm:p-5 border border-slate-200 rounded-xl space-y-4 bg-white">
              <div className="flex items-center gap-2 text-slate-900 font-semibold text-sm">
                <Send className="w-4 h-4 text-sky-500" />
                <span>Telegram bot integratsiyasi</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Student Telegram Card */}
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-800">
                      O‘quvchi Telegram hisobi
                    </span>
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
                      <div className="p-2 bg-white border border-slate-200 rounded-md flex items-center justify-between gap-2">
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
                      Yangi o‘quvchi havolasini yaratish
                    </Button>
                  )}
                </div>

                {/* Parent Telegram Card */}
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-800">
                      Ota-ona Telegram hisobi
                    </span>
                    {detail.parent?.telegram_connected ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Ulangan
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                        <XCircle className="w-3.5 h-3.5 text-slate-400" /> Ulanmagan
                      </span>
                    )}
                  </div>
                  {(detail.parent?.child_count ?? 0) > 1 && <p className="text-xs text-slate-500">Bu ota-onaga {detail.parent?.child_count} ta bola bog‘langan. Barcha bolalarning davomati shu Telegramga ism-familiyasi bilan boradi; ulanish havolasini yangilash barchasiga tegishli.</p>}

                  {detail.parent?.telegram_link?.deep_link && !detail.parent?.telegram_connected && (
                    <div className="space-y-2 pt-1">
                      <div className="p-2 bg-white border border-slate-200 rounded-md flex items-center justify-between gap-2">
                        <span className="text-[11px] font-mono text-slate-800 break-all select-all">
                          {detail.parent?.telegram_link.deep_link}
                        </span>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            handleCopyLink(detail.parent?.telegram_link!.deep_link, "parent")
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

                  {canEdit && detail.parent && (
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
              </div>
            </div>

            {/* 5. Monthly Attendance Statistics */}
            <div className="p-4 sm:p-5 border border-slate-200 rounded-xl space-y-4 bg-white">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <UserCheck className="w-4 h-4 text-emerald-600" />
                  <span className="text-slate-900 font-semibold text-sm">
                    Oylik davomat statistikasi
                  </span>
                </div>

                {/* Month Picker Controls */}
                <div className="flex items-center gap-1.5 self-end sm:self-auto">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePrevMonth}
                    disabled={isStatsLoading}
                    className="p-1.5"
                    aria-label="Oldingi oy"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <CalendarInput
                    type="month" required
                    value={selectedMonth}
                    onValueChange={handleMonthChange}
                    disabled={isStatsLoading}
                    className="px-2.5 py-1 text-xs font-medium border border-slate-300 rounded-lg bg-white text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                    aria-label="Oy tanlash"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleNextMonth}
                    disabled={isStatsLoading}
                    className="p-1.5"
                    aria-label="Keyingi oy"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {!canReadAttendance ? (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs flex items-center gap-2.5">
                  <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>
                    Davomat statistikasini ko‘rish uchun sizda yetarli ruxsat yo‘q (attendance:read huquqi talab qilinadi).
                  </span>
                </div>
              ) : isStatsLoading ? (
                <div className="py-6 flex items-center justify-center text-xs text-slate-500">
                  <RotateCcw className="w-4 h-4 animate-spin mr-2 text-slate-400" />
                  Davomat statistikasi yangilanmoqda...
                </div>
              ) : attendanceStats ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {/* Kelgan */}
                    <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-center">
                      <span className="text-[11px] font-semibold text-emerald-800 uppercase tracking-wider block">
                        Kelgan
                      </span>
                      <span className="text-2xl font-bold text-emerald-700 mt-1 block">
                        {attendanceStats.present_count}
                      </span>
                    </div>

                    {/* Kech qoldi */}
                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-center">
                      <span className="text-[11px] font-semibold text-amber-800 uppercase tracking-wider block">
                        Kech qoldi
                      </span>
                      <span className="text-2xl font-bold text-amber-700 mt-1 block">
                        {attendanceStats.late_count}
                      </span>
                    </div>

                    {/* Kelmagan */}
                    <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-center">
                      <span className="text-[11px] font-semibold text-rose-800 uppercase tracking-wider block">
                        Kelmagan
                      </span>
                      <span className="text-2xl font-bold text-rose-700 mt-1 block">
                        {attendanceStats.absent_count}
                      </span>
                    </div>

                    {/* Jami darslar */}
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-center">
                      <span className="text-[11px] font-semibold text-slate-600 uppercase tracking-wider block">
                        Jami darslar
                      </span>
                      <span className="text-2xl font-bold text-slate-800 mt-1 block">
                        {attendanceStats.total_lessons}
                      </span>
                    </div>
                  </div>

                  {/* Attendance Percentage / Summary */}
                  {attendanceStats.total_lessons > 0 ? (
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                      <div className="flex items-center gap-2 text-xs text-slate-700 font-medium">
                        <Percent className="w-4 h-4 text-emerald-600" />
                        <span>Davomat ko‘rsatkichi (Kelgan + Kech qolgan):</span>
                      </div>
                      <span
                        className={`text-sm font-bold ${
                          attendanceRate >= 80
                            ? "text-emerald-600"
                            : attendanceRate >= 60
                            ? "text-amber-600"
                            : "text-rose-600"
                        }`}
                      >
                        {attendanceRate}%
                      </span>
                    </div>
                  ) : (
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-500 text-xs text-center">
                      Tanlangan oy ({formatMonth(selectedMonth)}) uchun yakunlangan darslar mavjud emas.
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-500 text-xs text-center">
                  Davomat statistikasi mavjud emas.
                </div>
              )}
            </div>
          </div>
        ) : null}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={isDeleteDialogOpen}
        onClose={() => setIsDeleteDialogOpen(false)}
        title="O‘quvchini o‘chirish"
        description={`${detail?.first_name} ${detail?.last_name ?? ""} o‘quvchisini tizimdan o‘chirishni tasdiqlaysizmi?`}
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
          Ushbu amal o‘quvchini va uning barcha bog‘langan qaydlarini butunlay o‘chirib yuboradi.
        </p>
      </Modal>
    </>
  );
};

export const StudentDetailDrawer = StudentProfileModal;
