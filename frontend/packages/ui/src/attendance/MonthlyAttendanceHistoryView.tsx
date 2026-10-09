import React, { useEffect, useState, useMemo, useRef, useCallback } from "react";
import type { CurrentUser } from "../api/types";
import type { TeacherStudentItem } from "../teacher/types";
import { hasPermission, PERMISSIONS } from "../navigation/permissions";
import type { GroupMonthlyAttendanceHistoryResponse, MonthlyAttendanceRecord } from "./types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Button } from "../components/Button";
import { Card, CardContent } from "../components/Card";
import { Select } from "../components/Select";
import { Badge } from "../components/Badge";
import { LoadingState } from "../components/LoadingState";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { StudentProfileModal } from "../students/StudentDetailDrawer";
import { TeacherStudentProfileModal } from "../teacher/TeacherStudentDetailDrawer";
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  Clock,
  Lock,
  RefreshCw,
  CheckCircle2,
  XCircle,
} from "lucide-react";

export interface MonthlyAttendanceHistoryViewProps {
  portal: "admin" | "teacher";
  initialGroupId?: string;
  initialMonth?: string;
  groups?: Array<{ id: string; name: string }>;
  currentUser?: CurrentUser;
}

const MONTH_NAMES_UZ = [
  "Yanvar",
  "Fevral",
  "Mart",
  "Aprel",
  "May",
  "Iyun",
  "Iyul",
  "Avgust",
  "Sentabr",
  "Oktabr",
  "Noyabr",
  "Dekabr",
];

function formatMonthUz(monthStr: string): string {
  const parts = monthStr.split("-");
  if (parts.length !== 2) return monthStr;
  const year = parts[0];
  const mIndex = parseInt(parts[1], 10) - 1;
  const name = MONTH_NAMES_UZ[mIndex] || parts[1];
  return `${name} ${year}`;
}

function getAdjacentMonth(monthStr: string, offset: number): string {
  const parts = monthStr.split("-");
  if (parts.length !== 2) return monthStr;
  let year = parseInt(parts[0], 10);
  let month = parseInt(parts[1], 10) + offset;
  if (month < 1) {
    month = 12;
    year -= 1;
  } else if (month > 12) {
    month = 1;
    year += 1;
  }
  return `${year}-${String(month).padStart(2, "0")}`;
}

function getCurrentMonthString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

function formatDayHeader(dateStr: string): string {
  const parts = dateStr.split("-");
  if (parts.length === 3) {
    return parts[2];
  }
  return dateStr;
}

export const MonthlyAttendanceHistoryView: React.FC<MonthlyAttendanceHistoryViewProps> = ({
  portal,
  initialGroupId = "",
  initialMonth,
  groups: initialGroups,
  currentUser,
}) => {
  const [groups, setGroups] = useState<Array<{ id: string; name: string }>>(initialGroups || []);
  const [selectedGroupId, setSelectedGroupId] = useState<string>(initialGroupId);
  const [month, setMonth] = useState<string>(initialMonth || getCurrentMonthString());

  const [historyData, setHistoryData] = useState<GroupMonthlyAttendanceHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Selected student for Profile modal
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [selectedTeacherStudent, setSelectedTeacherStudent] = useState<TeacherStudentItem | null>(null);
  const canOpenProfile = portal === "teacher" || (currentUser && hasPermission(currentUser, PERMISSIONS.STUDENTS_READ));
  const openProfile = async (id: string) => {
    if (!canOpenProfile) return;
    if (portal === "admin") {
      setSelectedStudentId(id);
    } else {
      try {
        const data = await apiClient.get<TeacherStudentItem>(`/api/v1/teacher/students/${id}`, { params: { month } });
        setSelectedTeacherStudent(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "O‘quvchi profilini yuklab bo‘lmadi");
      }
    }
  };

  // Race condition protection ref
  const requestIdRef = useRef<number>(0);

  // Load groups if not provided
  useEffect(() => {
    if (initialGroups && initialGroups.length > 0) {
      setGroups(initialGroups);
      if (!selectedGroupId && initialGroups[0]) {
        setSelectedGroupId(initialGroups[0].id);
      }
      return;
    }

    const fetchGroups = async () => {
      try {
        if (portal === "admin") {
          const res = await apiClient.get<{ items: Array<{ id: string; name: string }> }>(
            "/api/v1/admin/groups",
            { params: { page_size: 100 } }
          );
          setGroups(res.items);
          if (!selectedGroupId && res.items.length > 0) {
            setSelectedGroupId(res.items[0].id);
          }
        } else {
          const res = await apiClient.get<Array<{ id: string; name: string }>>(
            "/api/v1/teacher/groups"
          );
          setGroups(res);
          if (!selectedGroupId && res.length > 0) {
            setSelectedGroupId(res[0].id);
          }
        }
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        }
      }
    };

    fetchGroups();
  }, [portal, initialGroups]);

  // Update selectedGroupId if initialGroupId changes
  useEffect(() => {
    if (initialGroupId) {
      setSelectedGroupId(initialGroupId);
    }
  }, [initialGroupId]);

  // Fetch history for selectedGroupId and month
  const fetchHistory = useCallback(async () => {
    if (!selectedGroupId) {
      setHistoryData(null);
      return;
    }

    const currentReqId = ++requestIdRef.current;
    setIsLoading(true);
    setHistoryData(null);
    setError(null);

    try {
      const endpoint =
        portal === "admin"
          ? `/api/v1/admin/groups/${selectedGroupId}/attendance/history`
          : `/api/v1/teacher/groups/${selectedGroupId}/attendance/history`;

      const res = await apiClient.get<GroupMonthlyAttendanceHistoryResponse>(endpoint, {
        params: { month },
      });

      // Ignore if a newer request was dispatched
      if (currentReqId !== requestIdRef.current) return;

      setHistoryData(res);
    } catch (err) {
      if (currentReqId !== requestIdRef.current) return;
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Davomat tarixini yuklashda xatolik yuz berdi");
      }
    } finally {
      if (currentReqId === requestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [portal, selectedGroupId, month]);

  useEffect(() => {
    fetchHistory();
    return () => { requestIdRef.current += 1; };
  }, [fetchHistory]);

  // Quick navigation handlers
  const handlePrevMonth = () => {
    setMonth((prev) => getAdjacentMonth(prev, -1));
  };

  const handleNextMonth = () => {
    setMonth((prev) => getAdjacentMonth(prev, 1));
  };

  const handleCurrentMonth = () => {
    setMonth(getCurrentMonthString());
  };

  // Map of (student_id + date) -> record
  const recordMap = useMemo(() => {
    const map = new Map<string, MonthlyAttendanceRecord>();
    if (historyData?.records) {
      for (const r of historyData.records) {
        map.set(`${r.student_id}_${r.date}`, r);
      }
    }
    return map;
  }, [historyData]);

  const dates = useMemo(() => {
    const [year, monthNumber] = month.split("-").map(Number);
    if (!year || !monthNumber) return [];
    return Array.from({ length: new Date(Date.UTC(year, monthNumber, 0)).getUTCDate() },
      (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`);
  }, [month]);
  const students = historyData?.students_summary || [];
  const summary = historyData?.summary;

  return (
    <div className="space-y-6">
      {/* Header & Filter Controls Card */}
      <Card>
        <CardContent className="p-4 sm:p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Calendar className="w-5 h-5 text-indigo-600" />
                <h2 className="text-lg font-bold text-slate-900">Oylik davomat tarixi</h2>
                <Badge variant="neutral" className="inline-flex items-center gap-1 text-xs">
                  <Lock className="w-3 h-3 text-slate-500" />
                  Faqat ko‘rish
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-slate-500 mt-1">
                Guruhning butun oy bo‘yicha yakunlangan darslar davomati va o‘quvchilar umumiy statistikasi
              </p>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={fetchHistory}
              disabled={isLoading || !selectedGroupId}
              className="self-start sm:self-auto"
            >
              <RefreshCw className={`w-4 h-4 mr-1.5 ${isLoading ? "animate-spin" : ""}`} />
              Yangilash
            </Button>
          </div>

          {/* Group and Month Selectors */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end pt-2 border-t border-slate-100">
            {/* Group Selector */}
            <div>
              <label htmlFor="group-history-select" className="block text-xs font-semibold text-slate-700 mb-1">
                Guruhni tanlang
              </label>
              <Select
                id="group-history-select"
                value={selectedGroupId}
                onChange={(e) => setSelectedGroupId(e.target.value)}
                className="w-full"
              >
                {groups.length === 0 && <option value="">Guruhlar yuklanmoqda...</option>}
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </Select>
            </div>

            {/* Month Picker */}
            <div>
              <label htmlFor="month-history-input" className="block text-xs font-semibold text-slate-700 mb-1">
                Oy (YYYY-MM)
              </label>
              <input
                id="month-history-input"
                type="month"
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Quick Month Navigation */}
            <div className="flex items-center gap-2 sm:col-span-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrevMonth}
                disabled={isLoading}
                title="Oldingi oy"
                className="flex-1 sm:flex-initial"
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                Oldingi
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleCurrentMonth}
                disabled={isLoading || month === getCurrentMonthString()}
                className="flex-1 sm:flex-initial"
              >
                Joriy oy
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleNextMonth}
                disabled={isLoading}
                title="Keyingi oy"
                className="flex-1 sm:flex-initial"
              >
                Keyingi
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <ErrorState
          title="Davomat tarixini yuklab bo‘lmadi"
          message={error}
          onRetry={fetchHistory}
        />
      )}

      {/* Loading State */}
      {isLoading && (
        <Card>
          <CardContent className="p-12">
            <LoadingState message="Oylik davomat jadvali yuklanmoqda..." />
          </CardContent>
        </Card>
      )}

      {/* Empty State: No Group Selected */}
      {!isLoading && !error && !selectedGroupId && (
        <Card>
          <CardContent className="p-8">
            <EmptyState
              title="Guruh tanlanmagan"
              description="Oylik davomat tarixini ko‘rish uchun yuqoridagi ro‘yxatdan guruhni tanlang."
            />
          </CardContent>
        </Card>
      )}

      {/* Main Content Area */}
      {!isLoading && !error && selectedGroupId && historyData && (
        <>
          {/* Monthly Summary Statistics Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span>Darslar soni</span>
                <Calendar className="w-4 h-4 text-indigo-500" />
              </div>
              <p className="text-xl sm:text-2xl font-bold text-slate-900 mt-1">
                {summary?.total_lessons || 0}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">{formatMonthUz(month)}</p>
            </div>

            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-emerald-600 text-xs font-medium">
                <span>Keldi</span>
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              </div>
              <p className="text-xl sm:text-2xl font-bold text-emerald-700 mt-1">
                {summary?.present_count || 0}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">Jami belgilangan</p>
            </div>

            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-amber-600 text-xs font-medium">
                <span>Kech qoldi</span>
                <Clock className="w-4 h-4 text-amber-500" />
              </div>
              <p className="text-xl sm:text-2xl font-bold text-amber-700 mt-1">
                {summary?.late_count || 0}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">Kechikishlar</p>
            </div>

            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-rose-600 text-xs font-medium">
                <span>Kelmadi</span>
                <XCircle className="w-4 h-4 text-rose-500" />
              </div>
              <p className="text-xl sm:text-2xl font-bold text-rose-700 mt-1">
                {summary?.absent_count || 0}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">Qatnashmagan</p>
            </div>
          </div>

          {/* Table Container or Empty Notice */}
          {historyData.dates.length === 0 ? (
            <Card>
              <CardContent className="p-8">
                <EmptyState
                  title="Ushbu oyda yakunlangan darslar yo‘q"
                  description={`${historyData.group_name} guruhi uchun ${formatMonthUz(month)} oyida hali yakunlangan davomat darslari mavjud emas.`}
                />
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {/* Matrix Table with Horizontal Scroll */}
              <div className="overflow-auto max-h-[65vh] border border-slate-200 rounded-lg bg-white shadow-xs">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 sticky top-0 z-20">
                    <tr>
                      {/* Sticky Student Name Column Header */}
                      <th
                        scope="col"
                        className="sticky left-0 bg-slate-50 z-20 px-4 py-3.5 text-left text-xs font-bold text-slate-700 uppercase tracking-wider border-r border-slate-200 min-w-[180px] sm:min-w-[220px] shadow-xs"
                      >
                        O‘quvchi
                      </th>

                      {/* Date Columns */}
                      {dates.map((dateStr) => (
                        <th
                          key={dateStr}
                          scope="col"
                          title={dateStr}
                          className="px-2 py-3 text-center text-xs font-bold text-slate-700 border-r border-slate-200 min-w-[44px]"
                        >
                          <div className="flex flex-col items-center">
                            <span>{formatDayHeader(dateStr)}</span>
                            <span className="text-[10px] text-slate-400 font-normal">kun</span>
                          </div>
                        </th>
                      ))}

                      {/* Summary Columns Header */}
                      <th
                        scope="col"
                        className="px-3 py-3 text-center text-xs font-bold text-emerald-700 bg-emerald-50/50 border-r border-slate-200 min-w-[60px]"
                        title="Kelgan darslar soni"
                      >
                        Keldi
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3 text-center text-xs font-bold text-amber-700 bg-amber-50/50 border-r border-slate-200 min-w-[60px]"
                        title="Kechikkan darslar soni"
                      >
                        Kech
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3 text-center text-xs font-bold text-rose-700 bg-rose-50/50 border-r border-slate-200 min-w-[60px]"
                        title="Kelmagan darslar soni"
                      >
                        Kelmadi
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3 text-center text-xs font-bold text-indigo-700 bg-indigo-50/50 min-w-[65px]"
                        title="Jami qatnashgan darslar / umumiy darslar"
                      >
                        Jami
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100 bg-white">
                    {students.map((student) => {
                      return (
                        <tr key={student.student_id} className="hover:bg-slate-50/80 transition-colors">
                          {/* Sticky Student Name Cell */}
                          <td className="sticky left-0 bg-white z-10 px-4 py-3 text-left font-medium text-slate-900 border-r border-slate-200 shadow-xs hover:bg-slate-50">
                            <button
                              type="button"
                              disabled={!canOpenProfile}
                              onClick={() => openProfile(student.student_id)}
                              className="text-left font-medium text-indigo-600 hover:text-indigo-800 hover:underline cursor-pointer focus:outline-hidden"
                              title="O‘quvchi to‘liq profilini ochish"
                            >
                              {student.student_name}
                            </button>
                          </td>

                          {/* Date status cells */}
                          {dates.map((dateStr) => {
                            const rec = recordMap.get(`${student.student_id}_${dateStr}`);

                            if (!rec) {
                              return (
                                <td
                                  key={dateStr}
                                  className="px-1 py-2 text-center border-r border-slate-100 bg-slate-50/30"
                                  title={`${student.student_name} - ${dateStr}: Dars belgilanmagan`}
                                  aria-label={`${dateStr}: Dars belgilanmagan`}
                                >
                                  <span className="text-slate-300 font-mono text-xs select-none">—</span>
                                </td>
                              );
                            }

                            if (rec.status === "present") {
                              return (
                                <td
                                  key={dateStr}
                                  className="px-1 py-2 text-center border-r border-slate-100 bg-emerald-50/20"
                                  title={`${student.student_name} - ${dateStr}: Keldi${rec.note ? `\nIzoh: ${rec.note}` : ""}`}
                                  aria-label={`${dateStr}: Keldi`}
                                >
                                  <div className="flex flex-col items-center justify-center">
                                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-700">
                                      <Check className="w-3.5 h-3.5" />
                                    </span>
                                    {rec.note && (
                                      <span className="text-[9px] text-slate-500 truncate max-w-[40px] mt-0.5" title={rec.note}>
                                        {rec.note}
                                      </span>
                                    )}
                                  </div>
                                </td>
                              );
                            }

                            if (rec.status === "late") {
                              return (
                                <td
                                  key={dateStr}
                                  className="px-1 py-2 text-center border-r border-slate-100 bg-amber-50/20"
                                  title={`${student.student_name} - ${dateStr}: Kech qoldi${rec.note ? `\nIzoh: ${rec.note}` : ""}`}
                                  aria-label={`${dateStr}: Kech qoldi`}
                                >
                                  <div className="flex flex-col items-center justify-center">
                                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-amber-100 text-amber-700">
                                      <Clock className="w-3.5 h-3.5" />
                                    </span>
                                    {rec.note && (
                                      <span className="text-[9px] text-slate-500 truncate max-w-[40px] mt-0.5" title={rec.note}>
                                        {rec.note}
                                      </span>
                                    )}
                                  </div>
                                </td>
                              );
                            }

                            // absent
                            return (
                              <td
                                key={dateStr}
                                className="px-1 py-2 text-center border-r border-slate-100 bg-rose-50/20"
                                title={`${student.student_name} - ${dateStr}: Kelmadi${rec.note ? `\nIzoh: ${rec.note}` : ""}`}
                                aria-label={`${dateStr}: Kelmadi`}
                              >
                                <div className="flex flex-col items-center justify-center">
                                  <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-rose-100 text-rose-700">
                                    <X className="w-3.5 h-3.5" />
                                  </span>
                                  {rec.note && (
                                    <span className="text-[9px] text-slate-500 truncate max-w-[40px] mt-0.5" title={rec.note}>
                                      {rec.note}
                                    </span>
                                  )}
                                </div>
                              </td>
                            );
                          })}

                          {/* Summary columns */}
                          <td className="px-3 py-3 text-center text-xs font-semibold text-emerald-700 bg-emerald-50/30 border-r border-slate-200">
                            {student.present_count}
                          </td>
                          <td className="px-3 py-3 text-center text-xs font-semibold text-amber-700 bg-amber-50/30 border-r border-slate-200">
                            {student.late_count}
                          </td>
                          <td className="px-3 py-3 text-center text-xs font-semibold text-rose-700 bg-rose-50/30 border-r border-slate-200">
                            {student.absent_count}
                          </td>
                          <td className="px-3 py-3 text-center text-xs font-bold text-slate-900 bg-indigo-50/30">
                            {student.attended_count}/{student.total_lessons}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Legend and Informational Footnote */}
              <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600">
                <div className="flex flex-wrap items-center gap-4 sm:gap-6">
                  <span className="font-semibold text-slate-700">Belgilar:</span>
                  <div className="flex items-center gap-1.5">
                    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-100 text-emerald-700">
                      <Check className="w-3 h-3" />
                    </span>
                    <span>Keldi</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-amber-100 text-amber-700">
                      <Clock className="w-3 h-3" />
                    </span>
                    <span>Kech qoldi</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-rose-100 text-rose-700">
                      <X className="w-3 h-3" />
                    </span>
                    <span>Kelmadi</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400 font-mono font-bold">—</span>
                    <span className="text-slate-500">Dars belgilanmagan</span>
                  </div>
                </div>

                <div className="text-slate-400">
                  O‘quvchi ismini bosib uning to‘liq profili va oylik statistikasini ochishingiz mumkin
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Student Profile Modal for Admin Portal */}
      {portal === "admin" && currentUser && canOpenProfile && (
        <StudentProfileModal
          isOpen={!!selectedStudentId}
          studentId={selectedStudentId}
          onClose={() => setSelectedStudentId(null)}
          currentUser={currentUser}
        />
      )}

      {/* Student Profile Modal for Teacher Portal */}
      {portal === "teacher" && (
        <TeacherStudentProfileModal
          isOpen={!!selectedTeacherStudent}
          student={selectedTeacherStudent}
          onClose={() => setSelectedTeacherStudent(null)}
        />
      )}
    </div>
  );
};
