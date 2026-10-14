import { formatDate, formatTime, tashkentToday } from "../lib/dates";
import React, { useState, useEffect, useCallback } from "react";
import type { CurrentUser } from "../api/types";
import type { AdminAttendanceItem, AdminAttendanceListResponse } from "./types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Card } from "../components/Card";
import { Button } from "../components/Button";
import { CalendarInput } from "../components/CalendarInput";
import { Select } from "../components/Select";
import { Badge } from "../components/Badge";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/Table";
import { AttendanceBadge } from "./AttendanceBadge";
import {
  RefreshCw,
  Calendar,
  CheckCircle2,
  XCircle,
  Clock,
  FilterX,
  Lock,
} from "lucide-react";
import { MonthlyAttendanceHistoryView } from "./MonthlyAttendanceHistoryView";
import { AdminChangesHistoryView } from "./AdminChangesHistoryView";
import { TeacherAttendanceView } from "../teacher/TeacherAttendanceView";
import type { AttendanceGroupOption } from "../teacher/TeacherAttendanceView";
import { canViewLogs, hasPermission, PERMISSIONS } from "../navigation/permissions";
import { AttendanceTemplateView } from "./AttendanceTemplateView";

export interface AdminAttendanceViewProps {
  currentUser: CurrentUser;
  defaultTab?: "matrix" | "list" | "mark";
}

export const AdminAttendanceView: React.FC<AdminAttendanceViewProps> = ({
  currentUser: _currentUser,
  defaultTab,
}) => {
  const canWrite = hasPermission(_currentUser, PERMISSIONS.ATTENDANCE_WRITE);
  const canAudit = canViewLogs(_currentUser);
  const [activeTab, setActiveTab] = useState<"matrix" | "list" | "mark" | "changes" | "template">(defaultTab || (canWrite ? "mark" : "matrix"));
  const [records, setRecords] = useState<AdminAttendanceItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 15;

  // Filters
  const [dateFilter, setDateFilter] = useState<string>("");
  const [groupIdFilter, setGroupIdFilter] = useState<string>("all");
  const [teacherIdFilter, setTeacherIdFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Options
  const [groups, setGroups] = useState<AttendanceGroupOption[]>([]);
  const [teachers, setTeachers] = useState<Array<{ id: string; name: string }>>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Load dropdown options once
  useEffect(() => {
    const loadOptions = async () => {
      try {
        const groupList = await apiClient.get<AttendanceGroupOption[]>("/api/v1/admin/attendance/groups");
        setGroups(groupList);
        setTeachers(Array.from(new Map(groupList.filter((group) => group.teacher_id).map((group) => [
          group.teacher_id!, { id: group.teacher_id!, name: group.teacher_name || "O‘qituvchi" },
        ])).values()));
      } catch {
        // Soft fail
      }
    };
    loadOptions();
  }, []);

  const loadAttendance = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
      };
      if (dateFilter) {
        params.date = dateFilter;
      }
      if (groupIdFilter !== "all") {
        params.group_id = groupIdFilter;
      }
      if (teacherIdFilter !== "all") {
        params.teacher_id = teacherIdFilter;
      }
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }

      const res = await apiClient.get<AdminAttendanceListResponse>("/api/v1/admin/attendance", {
        params,
      });
      setRecords(res.items);
      setTotal(res.total);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Davomat ma’lumotlarini yuklashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, dateFilter, groupIdFilter, teacherIdFilter, statusFilter]);

  useEffect(() => {
    loadAttendance();
  }, [loadAttendance]);

  const setTodayDate = () => {
    const today = tashkentToday();
    setDateFilter(today);
    setPage(1);
  };

  const handleResetFilters = () => {
    setDateFilter("");
    setGroupIdFilter("all");
    setTeacherIdFilter("all");
    setStatusFilter("all");
    setPage(1);
  };

  // Stats calculation on current records
  const presentCount = records.filter((r) => r.status === "present").length;
  const absentCount = records.filter((r) => r.status === "absent").length;
  const lateCount = records.filter((r) => r.status === "late").length;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Davomat</h1>
          <p className="text-sm text-slate-500 mt-1">
            Barcha guruhlar bo‘yicha davomat va oylik natijalar
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadAttendance()}
            disabled={isLoading}
            leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
          >
            Yangilash
          </Button>
        </div>
      </div>

      {/* View Mode Tabs */}
      <div className="flex flex-wrap border-b border-slate-200">
        {canWrite && <button type="button" onClick={() => setActiveTab("mark")}
          className={`py-2.5 px-4 text-sm font-medium border-b-2 ${activeTab === "mark" ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-500"}`}>
          Davomat olish
        </button>}
        <button
          type="button"
          onClick={() => setActiveTab("matrix")}
          className={`py-2.5 px-4 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
            activeTab === "matrix"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
          }`}
        >
          Oylik jadval (Guruh / Oy)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("list")}
          className={`py-2.5 px-4 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
            activeTab === "list"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
          }`}
        >
          Yozuvlar ro‘yxati
        </button>
        {canAudit && <button type="button" onClick={() => setActiveTab("changes")}
          className={`py-2.5 px-4 text-sm font-medium border-b-2 ${activeTab === "changes" ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-500"}`}>
          Audit tarixi
        </button>}
        {canWrite && <button type="button" onClick={() => setActiveTab("template")}
          className={`py-2.5 px-4 text-sm font-medium border-b-2 ${activeTab === "template" ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-500"}`}>Xabar shabloni</button>}
      </div>

      {activeTab === "template" && canWrite ? <AttendanceTemplateView currentUser={_currentUser} /> : activeTab === "changes" && canAudit ? <AdminChangesHistoryView groups={groups} /> : activeTab === "mark" && canWrite ? <TeacherAttendanceView portal="admin" /> : activeTab === "matrix" ? (
        <MonthlyAttendanceHistoryView
          portal="admin"
          groups={groups}
          currentUser={_currentUser}
        />
      ) : (
        <>
          {/* Filter and Search Bar */}
          <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="attendance-date" className="block text-xs font-medium text-slate-700">
                Sana
              </label>
              <button
                type="button"
                onClick={setTodayDate}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium"
              >
                Bugun
              </button>
            </div>
            <CalendarInput
              id="attendance-date"
              type="date"
              value={dateFilter}
              onValueChange={(iso) => {
                setDateFilter(iso);
                setPage(1);
              }}
            />
          </div>

          <div>
            <label htmlFor="attendance-group" className="block text-xs font-medium text-slate-700 mb-1">
              Guruh
            </label>
            <Select
              id="attendance-group"
              value={groupIdFilter}
              onChange={(e) => {
                setGroupIdFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "all", label: "Barcha guruhlar" },
                ...groups.map((g) => ({ value: g.id, label: g.name })),
              ]}
            />
          </div>

          <div>
            <label htmlFor="attendance-teacher" className="block text-xs font-medium text-slate-700 mb-1">
              O‘qituvchi
            </label>
            <Select
              id="attendance-teacher"
              value={teacherIdFilter}
              onChange={(e) => {
                setTeacherIdFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "all", label: "Barcha o‘qituvchilar" },
                ...teachers.map((t) => ({
                  value: t.id,
                  label: t.name,
                })),
              ]}
            />
          </div>

          <div>
            <label htmlFor="attendance-status" className="block text-xs font-medium text-slate-700 mb-1">
              Davomat holati
            </label>
            <Select
              id="attendance-status"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "all", label: "Barcha holatlar" },
                { value: "present", label: "Bor" },
                { value: "absent", label: "Yo‘q" },
                { value: "late", label: "Kechikdi" },
              ]}
            />
          </div>
        </div>

        {(dateFilter || groupIdFilter !== "all" || teacherIdFilter !== "all" || statusFilter !== "all") && (
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-end">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleResetFilters}
              leftIcon={<FilterX className="w-3.5 h-3.5" />}
              className="text-xs text-slate-500 hover:text-slate-800"
            >
              Filtrlarni tozalash
            </Button>
          </div>
        )}
      </Card>

      {/* Stats row */}
      {records.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white p-3 rounded-lg border border-slate-200">
            <div className="text-xs text-slate-500 font-medium">Jami yozuvlar</div>
            <div className="text-lg font-bold text-slate-900 mt-0.5">{total} ta</div>
          </div>
          <div className="bg-emerald-50/50 p-3 rounded-lg border border-emerald-200">
            <div className="text-xs text-emerald-700 font-medium flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Bor
            </div>
            <div className="text-lg font-bold text-emerald-800 mt-0.5">{presentCount} ta</div>
          </div>
          <div className="bg-rose-50/50 p-3 rounded-lg border border-rose-200">
            <div className="text-xs text-rose-700 font-medium flex items-center gap-1">
              <XCircle className="w-3.5 h-3.5 text-rose-600" /> Yo‘q
            </div>
            <div className="text-lg font-bold text-rose-800 mt-0.5">{absentCount} ta</div>
          </div>
          <div className="bg-amber-50/50 p-3 rounded-lg border border-amber-200">
            <div className="text-xs text-amber-700 font-medium flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-amber-600" /> Kechikdi
            </div>
            <div className="text-lg font-bold text-amber-800 mt-0.5">{lateCount} ta</div>
          </div>
        </div>
      )}

      {/* Error Alert */}
      {error && !isLoading && records.length > 0 && (
        <Alert variant="danger" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Main Content */}
      {isLoading && records.length === 0 ? (
        <LoadingState message="Davomat tarixi yuklanmoqda..." />
      ) : error && records.length === 0 ? (
        <ErrorState title="Davomatni yuklab bo‘lmadi" message={error} onRetry={loadAttendance} />
      ) : records.length === 0 ? (
        <EmptyState
          title="Davomat yozuvlari topilmadi"
          description="Tanlangan sana yoki filtrlar bo‘yicha davomat qaydlari mavjud emas."
        />
      ) : (
        <div className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sana</TableHead>
                <TableHead>O‘quvchi</TableHead>
                <TableHead>Guruh</TableHead>
                <TableHead>O‘qituvchi</TableHead>
                <TableHead>Holati</TableHead>
                <TableHead>Izoh</TableHead>
                <TableHead className="text-right">Yakunlangan</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((record) => (
                <TableRow key={record.attendance_id}>
                  <TableCell>
                    <div className="flex items-center gap-1.5 text-xs text-slate-800 font-medium">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      {formatDate(record.date)}
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                      {formatTime(record.marked_at)}
                    </div>
                  </TableCell>

                  <TableCell>
                    <span className="font-semibold text-slate-900 text-xs">
                      {record.student_name}
                    </span>
                  </TableCell>

                  <TableCell>
                    <span className="inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                      {record.group_name}
                    </span>
                  </TableCell>

                  <TableCell>
                    <span className="text-xs text-slate-600">{record.teacher_name}</span>
                  </TableCell>

                  <TableCell>
                    <AttendanceBadge status={record.status} />
                  </TableCell>

                  <TableCell>
                    {record.note ? (
                      <span className="text-xs text-slate-700 max-w-xs truncate block" title={record.note}>
                        {record.note}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400 italic">—</span>
                    )}
                  </TableCell>

                  <TableCell className="text-right">
                    {record.finalized ? (
                      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-medium" title="Davomat o‘qituvchi tomonidan tasdiqlangan va yakunlangan">
                        <Lock className="w-3 h-3 text-emerald-600" /> Yakunlangan
                      </span>
                    ) : (
                      <Badge variant="warning" size="sm">{record.source_imported ? "CSV qoralamasi" : "Qoralama"}</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Pagination */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-1 py-2 text-xs text-slate-600">
            <div>
              Jami: <span className="font-semibold text-slate-900">{total}</span> ta yozuv
              {totalPages > 1 && (
                <span>
                  {" "}(Sahifa: {page} / {totalPages})
                </span>
              )}
            </div>

            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1 || isLoading}
                  onClick={() => setPage(page - 1)}
                >
                  Oldingi
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages || isLoading}
                  onClick={() => setPage(page + 1)}
                >
                  Keyingi
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
        </>
      )}
    </div>
  );
};
