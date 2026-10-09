import React, { useState, useEffect } from "react";
import type { TeacherStudentItem } from "./types";
import { formatDaysOfWeek, formatPrice } from "../academic/types";
import { apiClient } from "../api/client";
import { Modal } from "../components/Modal";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import {
  Users,
  Phone,
  Calendar,
  Send,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Layers,
  Clock,
  DoorOpen,
  DollarSign,
  UserCheck,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Percent,
} from "lucide-react";

export interface TeacherStudentProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  student: TeacherStudentItem | null;
}

export type TeacherStudentDetailDrawerProps = TeacherStudentProfileModalProps;

function getAdjacentMonth(monthStr: string, delta: number): string {
  const parts = monthStr.split("-");
  const year = parseInt(parts[0], 10) || new Date().getFullYear();
  const month = (parseInt(parts[1], 10) || 1) - 1;
  const d = new Date(Date.UTC(year, month + delta, 1));
  const newY = d.getUTCFullYear();
  const newM = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${newY}-${newM}`;
}

export const TeacherStudentProfileModal: React.FC<TeacherStudentProfileModalProps> = ({
  isOpen,
  onClose,
  student,
}) => {
  const [detail, setDetail] = useState<TeacherStudentItem | null>(student);
  const [isStatsLoading, setIsStatsLoading] = useState<boolean>(false);
  const [selectedMonth, setSelectedMonth] = useState<string>(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });

  useEffect(() => {
    if (student) {
      setDetail(student);
    }
  }, [student]);

  useEffect(() => {
    if (isOpen && student?.id) {
      let isCurrent = true;
      setIsStatsLoading(true);
      apiClient
        .get<TeacherStudentItem>(
          `/api/v1/teacher/students/${student.id}?month=${selectedMonth}`
        )
        .then((data) => {
          if (isCurrent && data && !Array.isArray(data)) {
            setDetail(data);
          }
        })
        .catch((err) => {
          // If fetch fails or in tests without mock, detail remains the student prop
          console.debug("Failed to load student detail with stats", err);
        })
        .finally(() => {
          if (isCurrent) {
            setIsStatsLoading(false);
          }
        });
      return () => {
        isCurrent = false;
      };
    }
  }, [isOpen, student?.id, selectedMonth]);

  if (!isOpen || !student) {
    return null;
  }

  const currentData = (detail && !Array.isArray(detail)) ? detail : student;

  const handleMonthChange = (newMonth: string) => {
    setSelectedMonth(newMonth);
  };

  const handlePrevMonth = () => {
    const prev = getAdjacentMonth(selectedMonth, -1);
    handleMonthChange(prev);
  };

  const handleNextMonth = () => {
    const next = getAdjacentMonth(selectedMonth, 1);
    handleMonthChange(next);
  };

  const formattedDate = currentData.created_at
    ? new Date(currentData.created_at).toLocaleDateString("uz-UZ", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "-";

  const attendanceStats = currentData.attendance_stats;
  const attendanceRate =
    attendanceStats && attendanceStats.total_lessons > 0
      ? Math.round((attendanceStats.attended_count / attendanceStats.total_lessons) * 100)
      : 0;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <span>O‘quvchi ma’lumotlari</span>
          <Badge
            variant={currentData.status === "active" ? "success" : "neutral"}
            size="sm"
          >
            {currentData.status === "active" ? "Faol" : "Nofaol"}
          </Badge>
        </div>
      }
      description={`${currentData.first_name || ""} ${currentData.last_name || ""} bo‘yicha batafsil profil`}
      size="2xl"
      footer={
        <Button variant="outline" size="sm" onClick={onClose}>
          Yopish
        </Button>
      }
    >
      <div className="space-y-6">
        {/* 1. Student Profile Section */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 sm:p-5 space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-lg">
                {currentData.first_name?.[0] || "O"}
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  {currentData.first_name} {currentData.last_name}
                </h3>
                <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-500">
                  <Layers className="w-3.5 h-3.5 text-slate-400" />
                  <span>{currentData.group_name}</span>
                  <span>•</span>
                  <span>{currentData.age == null ? (currentData.school_grade ?? "Yosh kiritilmagan") : `${currentData.age} yoshda`}</span>
                </div>
              </div>
            </div>

            <Badge
              variant={currentData.status === "active" ? "success" : "neutral"}
              size="sm"
            >
              {currentData.status === "active" ? "Faol" : "Nofaol"}
            </Badge>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3 border-t border-slate-200/60 text-xs">
            <div>
              <p className="text-slate-500 font-medium mb-0.5">Telefon raqami</p>
              <a
                href={currentData.phone ? `tel:${currentData.phone}` : undefined}
                className="inline-flex items-center gap-1.5 text-slate-900 font-semibold hover:text-emerald-600 transition-colors"
              >
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                <span>{currentData.phone ?? "Kiritilmagan"}</span>
              </a>
            </div>

            <div>
              <p className="text-slate-500 font-medium mb-0.5">Telegram holati</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                {currentData.telegram_connected ? (
                  <Badge variant="success" size="sm">
                    <Send className="w-3 h-3 mr-1 inline" />
                    Telegram ulangan
                  </Badge>
                ) : (
                  <Badge variant="neutral" size="sm">
                    Telegram ulanmagan
                  </Badge>
                )}
              </div>
            </div>

            <div>
              <p className="text-slate-500 font-medium mb-0.5">Qo‘shilgan sana</p>
              <div className="flex items-center gap-1.5 text-slate-700 font-medium mt-0.5">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span>{formattedDate}</span>
              </div>
            </div>
          </div>
        </div>

        {/* 2. Group & Lesson Details */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5 space-y-3 shadow-2xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
              <Layers className="w-4 h-4 text-emerald-600" />
              <span>Guruh va dars tafsilotlari</span>
            </div>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              {currentData.group_name}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs pt-1">
            <div className="p-2.5 bg-slate-50 rounded-lg">
              <span className="text-slate-500 block mb-0.5">Fan</span>
              <span className="font-semibold text-slate-900">
                {currentData.subject_name || "-"}
              </span>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg">
              <span className="text-slate-500 block mb-0.5">O‘qituvchi</span>
              <span className="font-semibold text-slate-900">
                {currentData.teacher_name || "-"}
              </span>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg">
              <span className="text-slate-500 block mb-0.5">Oylik to‘lov</span>
              <span className="font-semibold text-slate-900 flex items-center gap-1">
                <DollarSign className="w-3.5 h-3.5 text-slate-400" />
                {formatPrice(currentData.monthly_price)}
              </span>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg">
              <span className="text-slate-500 block mb-0.5">Dars kunlari</span>
              <span className="font-semibold text-slate-900">
                {currentData.days_of_week
                  ? formatDaysOfWeek(currentData.days_of_week)
                  : "-"}
              </span>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg">
              <span className="text-slate-500 block mb-0.5">Dars vaqti</span>
              <span className="font-semibold text-slate-900 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                {currentData.start_time ? currentData.start_time.slice(0, 5) : "-"} –{" "}
                {currentData.end_time ? currentData.end_time.slice(0, 5) : "-"}
              </span>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg">
              <span className="text-slate-500 block mb-0.5">Xona</span>
              <span className="font-semibold text-slate-900 flex items-center gap-1">
                <DoorOpen className="w-3.5 h-3.5 text-slate-400" />
                {currentData.room_number || "-"}
              </span>
            </div>
          </div>
        </div>

        {/* 3. Parent Section */}
        {(currentData.school_grade || currentData.import_notes?.length) && (
          <div className="p-4 border border-slate-200 rounded-xl space-y-2 text-sm">
            {currentData.school_grade && <p><strong>Sinf:</strong> {currentData.school_grade}</p>}
            {!!currentData.import_notes?.length && <div><strong>Manbadagi izohlar</strong>{currentData.import_notes.map((note, index) => <p key={index}>{note}</p>)}</div>}
          </div>
        )}
        <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5 space-y-4 shadow-2xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
              <Users className="w-4 h-4 text-emerald-600" />
              <span>Ota-ona ma’lumotlari</span>
            </div>
            {currentData.parent?.telegram_connected ? (
              <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Ulangan
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                <XCircle className="w-3.5 h-3.5 text-slate-400" /> Ulanmagan
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3 bg-slate-50 rounded-lg space-y-1">
              <p className="text-slate-500 font-medium">F.I.Sh</p>
              <p className="text-sm font-semibold text-slate-900">
                {currentData.parent?.first_name ?? "Kiritilmagan"} {currentData.parent?.last_name}
              </p>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg space-y-1">
              <p className="text-slate-500 font-medium">Aloqa telefoni</p>
              <a
                href={currentData.parent?.phone ? `tel:${currentData.parent.phone}` : undefined}
                className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-900 hover:text-emerald-600 transition-colors"
              >
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                <span>{currentData.parent?.phone ?? "Kiritilmagan"}</span>
              </a>
            </div>
          </div>

          <div>
            <p className="text-xs text-slate-500 font-medium mb-1">Telegram xabarnoma holati</p>
            {currentData.parent?.telegram_connected ? (
              <div className="flex items-start gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-900 text-xs">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold block">Telegram hisobi ulangan</span>
                  <span className="text-emerald-700 text-[11px]">
                    Davomat natijalari (Bor/Yo‘q/Kechikdi) avtomatik ravishda ushbu hisobga yuboriladi.
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 text-xs">
                <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold block">Telegram ulanmagan</span>
                  <span className="text-amber-700 text-[11px]">
                    Ota-ona botga ulanmagan. Davomat xabarnomalari ota-ona hisobini bog‘lagandan keyin yetkaziladi.
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 4. Monthly Attendance Statistics */}
        <div className="p-4 sm:p-5 border border-slate-200 rounded-xl space-y-4 bg-white shadow-2xs">
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
              <input
                type="month"
                value={selectedMonth}
                onChange={(e) => {
                  if (e.target.value) handleMonthChange(e.target.value);
                }}
                disabled={isStatsLoading}
                className="px-2.5 py-1 text-xs font-medium border border-slate-300 rounded-lg bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
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

          {isStatsLoading ? (
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
                  Tanlangan oy ({selectedMonth}) uchun yakunlangan darslar mavjud emas.
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
    </Modal>
  );
};

export const TeacherStudentDetailDrawer = TeacherStudentProfileModal;
