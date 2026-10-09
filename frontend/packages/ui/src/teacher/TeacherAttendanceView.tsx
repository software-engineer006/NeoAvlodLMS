import React, { useEffect, useState, useMemo, useCallback } from "react";
import type {
  TeacherGroupItem,
  TeacherAttendanceSheet,
  TeacherAttendanceStatus,
  TeacherDraftItemIn,
} from "./types";
import { apiClient } from "../api/client";
import { Button } from "../components/Button";
import { Card, CardContent } from "../components/Card";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Modal } from "../components/Modal";
import { Alert } from "../components/Alert";
import { LoadingState } from "../components/LoadingState";
import { EmptyState } from "../components/EmptyState";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "../components/Table";
import {
  Check,
  X,
  Clock,
  CheckCircle2,
  AlertCircle,
  CalendarCheck,
  Save,
  Lock,
  Calendar,
  AlertTriangle,
} from "lucide-react";

export interface TeacherAttendanceViewProps {
  preselectedGroupId?: string;
  initialDate?: string;
  groups?: TeacherGroupItem[];
  onSelectGroupChange?: (groupId: string) => void;
}

interface LocalEntryState {
  student_id: string;
  student_first_name: string;
  student_last_name: string;
  status: TeacherAttendanceStatus | null;
  note: string;
}

export const TeacherAttendanceView: React.FC<TeacherAttendanceViewProps> = ({
  preselectedGroupId,
  initialDate,
  groups: initialGroups,
  onSelectGroupChange,
}) => {
  const [groups, setGroups] = useState<TeacherGroupItem[]>(initialGroups || []);
  const [selectedGroupId, setSelectedGroupId] = useState<string>(preselectedGroupId || "");

  const todayStr = useMemo(() => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }, []);

  const [date, setDate] = useState<string>(initialDate || todayStr);
  const [sheet, setSheet] = useState<TeacherAttendanceSheet | null>(null);
  const [entries, setEntries] = useState<Record<string, LocalEntryState>>({});
  const [initialEntriesSnapshot, setInitialEntriesSnapshot] = useState<string>("");

  const [isLoadingGroups, setIsLoadingGroups] = useState<boolean>(false);
  const [isLoadingSheet, setIsLoadingSheet] = useState<boolean>(false);
  const [isSavingDraft, setIsSavingDraft] = useState<boolean>(false);
  const [isFinalizing, setIsFinalizing] = useState<boolean>(false);

  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isConfirmFinalizeOpen, setIsConfirmFinalizeOpen] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Unsaved changes confirmation modal
  const [isUnsavedModalOpen, setIsUnsavedModalOpen] = useState<boolean>(false);
  const [pendingNavigation, setPendingNavigation] = useState<{
    type: "group" | "date";
    value: string;
  } | null>(null);

  const isDirty = useMemo(() => {
    if (sheet?.finalized) return false;
    if (!initialEntriesSnapshot) return false;
    return JSON.stringify(entries) !== initialEntriesSnapshot;
  }, [entries, initialEntriesSnapshot, sheet?.finalized]);

  // Fetch groups if not provided
  const fetchGroups = async () => {
    setIsLoadingGroups(true);
    try {
      const data = await apiClient.get<TeacherGroupItem[]>("/api/v1/teacher/groups");
      setGroups(data);
      if (!selectedGroupId && data.length > 0) {
        const defaultId = preselectedGroupId || data[0].id;
        setSelectedGroupId(defaultId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Guruhlarni yuklashda xatolik yuz berdi");
    } finally {
      setIsLoadingGroups(false);
    }
  };

  useEffect(() => {
    if (!initialGroups || initialGroups.length === 0) {
      fetchGroups();
    } else {
      setGroups(initialGroups);
      if (!selectedGroupId && initialGroups.length > 0) {
        setSelectedGroupId(preselectedGroupId || initialGroups[0].id);
      }
    }
  }, [initialGroups, preselectedGroupId]);

  // Fetch Attendance Sheet
  const fetchAttendanceSheet = useCallback(async (groupId: string, targetDate: string) => {
    if (!groupId || !targetDate) return;
    setIsLoadingSheet(true);
    setError(null);
    setSuccessMessage(null);
    setValidationError(null);

    try {
      const data = await apiClient.get<TeacherAttendanceSheet>(
        `/api/v1/teacher/groups/${groupId}/attendance?date=${targetDate}`
      );
      setSheet(data);

      const localMap: Record<string, LocalEntryState> = {};
      data.items.forEach((item) => {
        localMap[item.student_id] = {
          student_id: item.student_id,
          student_first_name: item.student_first_name,
          student_last_name: item.student_last_name ?? "",
          status: item.status,
          note: item.note || "",
        };
      });
      setEntries(localMap);
      setInitialEntriesSnapshot(JSON.stringify(localMap));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Davomat ma’lumotlarini yuklashda xatolik yuz berdi");
    } finally {
      setIsLoadingSheet(false);
    }
  }, []);

  useEffect(() => {
    if (selectedGroupId && date) {
      fetchAttendanceSheet(selectedGroupId, date);
    }
  }, [selectedGroupId, date, fetchAttendanceSheet]);

  const applyGroupChange = (newGroupId: string) => {
    setSelectedGroupId(newGroupId);
    if (onSelectGroupChange) {
      onSelectGroupChange(newGroupId);
    }
  };

  const applyDateChange = (newDate: string) => {
    setDate(newDate);
  };

  const handleGroupSelect = (newGroupId: string) => {
    if (newGroupId === selectedGroupId) return;
    if (isDirty) {
      setPendingNavigation({ type: "group", value: newGroupId });
      setIsUnsavedModalOpen(true);
      return;
    }
    applyGroupChange(newGroupId);
  };

  const handleDateChange = (newDate: string) => {
    if (newDate === date) return;
    if (isDirty) {
      setPendingNavigation({ type: "date", value: newDate });
      setIsUnsavedModalOpen(true);
      return;
    }
    applyDateChange(newDate);
  };

  const handleTodayClick = () => {
    if (date === todayStr) return;
    handleDateChange(todayStr);
  };

  const handleDiscardAndProceed = () => {
    if (pendingNavigation) {
      if (pendingNavigation.type === "group") {
        applyGroupChange(pendingNavigation.value);
      } else {
        applyDateChange(pendingNavigation.value);
      }
      setPendingNavigation(null);
    }
    setIsUnsavedModalOpen(false);
  };

  const handleStatusChange = (studentId: string, status: TeacherAttendanceStatus) => {
    if (sheet?.finalized) return;
    setEntries((prev) => {
      const existing = prev[studentId];
      if (!existing) return prev;
      return {
        ...prev,
        [studentId]: {
          ...existing,
          status: existing.status === status ? null : status,
        },
      };
    });
  };

  const handleNoteChange = (studentId: string, note: string) => {
    if (sheet?.finalized) return;
    setEntries((prev) => {
      const existing = prev[studentId];
      if (!existing) return prev;
      return {
        ...prev,
        [studentId]: {
          ...existing,
          note: note.slice(0, 2000),
        },
      };
    });
  };

  const handleMarkAllPresent = () => {
    if (sheet?.finalized) return;
    setEntries((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((id) => {
        next[id] = { ...next[id], status: "present" };
      });
      return next;
    });
  };

  // Summary counts
  const counts = useMemo(() => {
    const list = Object.values(entries);
    const total = list.length;
    const present = list.filter((e) => e.status === "present").length;
    const absent = list.filter((e) => e.status === "absent").length;
    const late = list.filter((e) => e.status === "late").length;
    const unmarked = list.filter((e) => !e.status).length;
    return { total, present, absent, late, unmarked };
  }, [entries]);

  // Save Draft
  const handleSaveDraft = async () => {
    if (!selectedGroupId || isSavingDraft || isFinalizing || sheet?.finalized) return false;
    setError(null);
    setSuccessMessage(null);

    const itemsToSave: TeacherDraftItemIn[] = Object.values(entries)
      .filter((e) => e.status !== null)
      .map((e) => ({
        student_id: e.student_id,
        status: e.status as TeacherAttendanceStatus,
        note: e.note.trim() ? e.note.trim() : null,
      }));

    if (itemsToSave.length === 0) {
      setError("Qoralama sifatida saqlash uchun kamida bitta o‘quvchi holatini belgilang");
      return false;
    }

    setIsSavingDraft(true);
    try {
      const updatedSheet = await apiClient.post<TeacherAttendanceSheet>(
        `/api/v1/teacher/groups/${selectedGroupId}/attendance/draft`,
        {
          date,
          items: itemsToSave,
        }
      );
      setSheet(updatedSheet);
      setInitialEntriesSnapshot(JSON.stringify(entries));
      setSuccessMessage("Davomat qoralamasi muvaffaqiyatli saqlandi.");
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Qoralamani saqlashda xatolik yuz berdi");
      return false;
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleSaveAndProceed = async () => {
    const saved = await handleSaveDraft();
    if (saved && pendingNavigation) {
      if (pendingNavigation.type === "group") {
        applyGroupChange(pendingNavigation.value);
      } else {
        applyDateChange(pendingNavigation.value);
      }
      setPendingNavigation(null);
      setIsUnsavedModalOpen(false);
    }
  };

  // Open Finalize Dialog
  const handleOpenFinalizeModal = () => {
    setError(null);
    setValidationError(null);

    if (counts.unmarked > 0) {
      setValidationError(
        `Davomatni yakunlash uchun barcha o‘quvchilar belgilanadi (${counts.unmarked} nafar o‘quvchi belgilanmagan). Iltimos, barcha o‘quvchilarga Keldi, Kech qoldi yoki Kelmadi holatini belgilang.`
      );
    }
    setIsConfirmFinalizeOpen(true);
  };

  // Finalize Attendance
  const handleConfirmFinalize = async () => {
    if (!selectedGroupId || isFinalizing || isSavingDraft || counts.unmarked > 0) return;
    setError(null);
    setIsFinalizing(true);

    const itemsToSubmit: TeacherDraftItemIn[] = Object.values(entries).map((e) => ({
      student_id: e.student_id,
      status: e.status as TeacherAttendanceStatus,
      note: e.note.trim() ? e.note.trim() : null,
    }));

    try {
      const finalizedSheet = await apiClient.post<TeacherAttendanceSheet>(
        `/api/v1/teacher/groups/${selectedGroupId}/attendance/finalize`,
        {
          date,
          items: itemsToSubmit,
        }
      );
      setSheet(finalizedSheet);
      setInitialEntriesSnapshot(JSON.stringify(entries));
      setIsConfirmFinalizeOpen(false);
      setSuccessMessage(
        "Davomat muvaffaqiyatli yakunlandi! Ota-onalarga bildirishnomalar yuborish navbatiga qo‘yildi."
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Davomatni yakunlashda xatolik yuz berdi");
      setIsConfirmFinalizeOpen(false);
    } finally {
      setIsFinalizing(false);
    }
  };

  if (isLoadingGroups && groups.length === 0) {
    return <LoadingState message="Guruhlar yuklanmoqda..." />;
  }

  if (groups.length === 0) {
    return (
      <EmptyState
        title="Guruhlar biriktirilmagan"
        description="Sizga hali hech qanday guruh biriktirilmagan. Davomat olish uchun avval guruh biriktirilishi lozim."
      />
    );
  }

  const selectedGroup = groups.find((g) => g.id === selectedGroupId);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Davomat belgilash
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Guruh o‘quvchilarining darsdagi ishtirokini belgilash, qoralama saqlash va yakunlash
          </p>
        </div>

        <div className="flex items-center gap-2">
          {sheet?.finalized ? (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-xs font-semibold">
              <Lock className="w-4 h-4 text-emerald-600" />
              <span>Davomat yakunlangan (Readonly)</span>
            </div>
          ) : isDirty ? (
            <div className="flex items-center gap-1.5 px-3 py-1 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs font-medium">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
              <span>Saqlanmagan o‘zgarishlar bor</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-3 py-1 bg-slate-100 rounded-lg text-slate-600 text-xs font-medium">
              <Check className="w-3.5 h-3.5 text-slate-500" />
              <span>Saqlangan</span>
            </div>
          )}
        </div>
      </div>

      {/* Group & Date Selector Card */}
      <Card>
        <CardContent className="p-5 flex flex-col md:flex-row items-stretch md:items-end gap-4">
          <div className="flex-1">
            <Select
              label="Guruhni tanlang"
              value={selectedGroupId}
              onChange={(e) => handleGroupSelect(e.target.value)}
              options={groups.map((g) => ({
                value: g.id,
                label: `${g.name} (${g.subject?.name || "Fan yo‘q"})`,
              }))}
            />
          </div>

          <div className="w-full md:w-60">
            <Input
              type="date"
              label="Dars sanasi"
              value={date}
              onChange={(e) => handleDateChange(e.target.value)}
              leftAddon={<Calendar className="w-4 h-4 text-slate-400" />}
            />
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={handleTodayClick}
              disabled={date === todayStr}
            >
              Bugun
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Alerts */}
      {error && (
        <Alert variant="danger" title="Xatolik" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {successMessage && (
        <Alert variant="success" title="Muvaffaqiyatli" onDismiss={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {sheet?.finalized && (
        <Alert variant="info" title="Davomat yakunlangan">
          Ushbu sana (<strong>{date}</strong>) uchun davomat yakunlangan va ota-onalarga Telegram
          bildirishnomalari yuborilgan. Ma’lumotlar faqat o‘qish rejimida ko‘rsatilmoqda.
        </Alert>
      )}

      {/* Summary Counts Card */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <Card>
          <CardContent className="p-3 text-center">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
              Jami
            </span>
            <p className="text-xl font-bold text-slate-900 mt-0.5">{counts.total}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-3 text-center">
            <span className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wide">
              Keldi
            </span>
            <p className="text-xl font-bold text-emerald-600 mt-0.5">{counts.present}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-3 text-center">
            <span className="text-[11px] font-semibold text-amber-700 uppercase tracking-wide">
              Kech qoldi
            </span>
            <p className="text-xl font-bold text-amber-600 mt-0.5">{counts.late}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-3 text-center">
            <span className="text-[11px] font-semibold text-rose-700 uppercase tracking-wide">
              Kelmadi
            </span>
            <p className="text-xl font-bold text-rose-600 mt-0.5">{counts.absent}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-3 text-center col-span-2 sm:col-span-1">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
              Belgilanmagan
            </span>
            <p
              className={`text-xl font-bold mt-0.5 ${
                counts.unmarked > 0 ? "text-amber-600" : "text-slate-400"
              }`}
            >
              {counts.unmarked}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Table & Actions */}
      {isLoadingSheet ? (
        <LoadingState message="Davomat varaqasi yuklanmoqda..." />
      ) : Object.keys(entries).length === 0 ? (
        <EmptyState
          title="O‘quvchilar mavjud emas"
          description="Tanlangan guruhda faol o‘quvchilar mavjud emas."
        />
      ) : (
        <div className="space-y-4">
          {/* Quick Mark All Bar */}
          {!sheet?.finalized && (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50 p-3 sm:p-4 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-600">
                <span className="font-semibold text-slate-800">Davomat holati: </span>
                <span>{counts.total - counts.unmarked} / {counts.total} nafar o‘quvchi belgilangan</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleMarkAllPresent}
                leftIcon={<Check className="w-4 h-4 text-emerald-600" />}
                className="self-start sm:self-auto"
              >
                Barchasi keldi
              </Button>
            </div>
          )}

          {/* Responsive Table View */}
          <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-56 sm:w-64 whitespace-nowrap">O‘quvchi F.I.Sh</TableHead>
                  <TableHead className="w-72 sm:w-80 whitespace-nowrap">Davomat holati</TableHead>
                  <TableHead className="min-w-[200px]">Izoh (Sabab yoki kechikish)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.values(entries).map((entry) => {
                  const isPresent = entry.status === "present";
                  const isAbsent = entry.status === "absent";
                  const isLate = entry.status === "late";

                  return (
                    <TableRow key={entry.student_id}>
                      <TableCell>
                        <div className="font-semibold text-slate-900 whitespace-nowrap">
                          {entry.student_first_name} {entry.student_last_name}
                        </div>
                      </TableCell>

                      <TableCell>
                        <div className="inline-flex items-center gap-1.5 p-1 bg-slate-100 rounded-xl">
                          {/* Keldi Button */}
                          <button
                            type="button"
                            disabled={sheet?.finalized}
                            onClick={() => handleStatusChange(entry.student_id, "present")}
                            title="Keldi"
                            className={`px-3 sm:px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                              isPresent
                                ? "bg-emerald-600 text-white shadow-xs ring-2 ring-emerald-600/30"
                                : "text-slate-700 hover:text-emerald-700 hover:bg-slate-200/80"
                            } disabled:opacity-70 disabled:cursor-not-allowed`}
                          >
                            <Check className="w-4 h-4" />
                            <span>Keldi</span>
                          </button>

                          {/* Kech qoldi Button */}
                          <button
                            type="button"
                            disabled={sheet?.finalized}
                            onClick={() => handleStatusChange(entry.student_id, "late")}
                            title="Kech qoldi"
                            className={`px-3 sm:px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                              isLate
                                ? "bg-amber-500 text-white shadow-xs ring-2 ring-amber-500/30"
                                : "text-slate-700 hover:text-amber-700 hover:bg-slate-200/80"
                            } disabled:opacity-70 disabled:cursor-not-allowed`}
                          >
                            <Clock className="w-4 h-4" />
                            <span>Kech qoldi</span>
                          </button>

                          {/* Kelmadi Button */}
                          <button
                            type="button"
                            disabled={sheet?.finalized}
                            onClick={() => handleStatusChange(entry.student_id, "absent")}
                            title="Kelmadi"
                            className={`px-3 sm:px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                              isAbsent
                                ? "bg-rose-600 text-white shadow-xs ring-2 ring-rose-600/30"
                                : "text-slate-700 hover:text-rose-700 hover:bg-slate-200/80"
                            } disabled:opacity-70 disabled:cursor-not-allowed`}
                          >
                            <X className="w-4 h-4" />
                            <span>Kelmadi</span>
                          </button>
                        </div>
                      </TableCell>

                      <TableCell>
                        {sheet?.finalized ? (
                          <span className="text-xs text-slate-600 italic">
                            {entry.note || "Izoh kiritilmagan"}
                          </span>
                        ) : (
                          <Input
                            type="text"
                            placeholder="Izoh yozish (ixtiyoriy)..."
                            value={entry.note}
                            onChange={(e) =>
                              handleNoteChange(entry.student_id, e.target.value)
                            }
                            maxLength={2000}
                          />
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          {/* Action Bar */}
          {!sheet?.finalized && (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
              <div className="text-xs text-slate-500">
                {counts.unmarked > 0 ? (
                  <span className="text-amber-600 font-semibold flex items-center gap-1">
                    <AlertCircle className="w-4 h-4" />
                    Yakunlash uchun barcha o‘quvchilar belgilanishi shart ({counts.unmarked} nafar qoldi)
                  </span>
                ) : (
                  <span className="text-emerald-700 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" />
                    Barcha o‘quvchilar belgilandi. Yakunlashga tayyor.
                  </span>
                )}
              </div>

              <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
                <Button
                  variant="outline"
                  onClick={handleSaveDraft}
                  isLoading={isSavingDraft}
                  disabled={isFinalizing || isSavingDraft}
                  leftIcon={<Save className="w-4 h-4" />}
                >
                  Qoralama saqlash
                </Button>

                <Button
                  variant="primary"
                  onClick={handleOpenFinalizeModal}
                  disabled={isFinalizing || isSavingDraft}
                  leftIcon={<CalendarCheck className="w-4 h-4" />}
                >
                  Davomatni yakunlash
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Confirmation Modal for Finalize */}
      <Modal
        isOpen={isConfirmFinalizeOpen}
        onClose={() => setIsConfirmFinalizeOpen(false)}
        title="Davomatni yakunlash"
        description={`${selectedGroup?.name} guruhi bo‘yicha ${date} sanasidagi davomat`}
        footer={
          <div className="flex items-center justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => setIsConfirmFinalizeOpen(false)}
              disabled={isFinalizing}
            >
              Bekor qilish
            </Button>
            <Button
              variant="primary"
              onClick={handleConfirmFinalize}
              isLoading={isFinalizing}
              disabled={isFinalizing || counts.unmarked > 0}
            >
              Tasdiqlash va yakunlash
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          {validationError ? (
            <Alert variant="danger" title="Belgilanmagan o‘quvchilar mavjud">
              {validationError}
            </Alert>
          ) : (
            <>
              <p className="text-sm text-slate-600 leading-relaxed">
                Davomat yakunlangach, barcha ota-onalarga Telegram boti orqali farzandining
                bugungi darsdagi ishtiroki haqida avtomatik xabar yuboriladi.
              </p>
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <span>
                  <strong>Diqqat:</strong> Yakunlangandan so‘ng ushbu sana bo‘yicha davomatni
                  o‘zgartirib bo‘lmaydi.
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-xs pt-1">
                <div className="p-2 bg-emerald-50 rounded-lg text-emerald-800">
                  <span className="font-bold block text-sm">{counts.present}</span>
                  <span>Keldi</span>
                </div>
                <div className="p-2 bg-amber-50 rounded-lg text-amber-800">
                  <span className="font-bold block text-sm">{counts.late}</span>
                  <span>Kech qoldi</span>
                </div>
                <div className="p-2 bg-rose-50 rounded-lg text-rose-800">
                  <span className="font-bold block text-sm">{counts.absent}</span>
                  <span>Kelmadi</span>
                </div>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* Unsaved Changes Warning Modal */}
      <Modal
        isOpen={isUnsavedModalOpen}
        onClose={() => {
          setIsUnsavedModalOpen(false);
          setPendingNavigation(null);
        }}
        title="Saqlanmagan o‘zgarishlar mavjud"
        description="Davomat varaqasidagi o‘zgarishlar hali saqlanmagan"
        size="md"
        footer={
          <div className="flex flex-col sm:flex-row items-center justify-end gap-2 w-full">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setIsUnsavedModalOpen(false);
                setPendingNavigation(null);
              }}
              className="w-full sm:w-auto"
            >
              Bekor qilish
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={handleDiscardAndProceed}
              className="w-full sm:w-auto"
            >
              O‘zgarishlarni bekor qilish va o‘tish
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSaveAndProceed}
              isLoading={isSavingDraft}
              className="w-full sm:w-auto"
            >
              Avval saqlash
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            Siz davomatga kiritgan o‘zgarishlarni qoralama sifatida saqlamadingiz yoki yakunlamadingiz. Guruh yoki sanani almashtirsangiz, ushbu o‘zgarishlar yo‘qoladi.
          </p>
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              Davom etishdan oldin o‘zgarishlarni qoralama sifatida saqlashni tavsiya qilamiz.
            </span>
          </div>
        </div>
      </Modal>
    </div>
  );
};
