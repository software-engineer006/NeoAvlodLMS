import React, { useState, useEffect } from "react";
import type { StudentItem, StudentDetailItem, StudentTransferInput } from "./types";
import { studentEnrollments } from "./types";
import type { StudentGroupOption } from "../academic/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Modal } from "../components/Modal";
import { Select } from "../components/Select";
import { Input } from "../components/Input";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { ArrowRightLeft } from "lucide-react";

export interface StudentTransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  student: StudentItem | null;
  onSuccess: (updated: StudentDetailItem) => void;
}

export const StudentTransferModal: React.FC<StudentTransferModalProps> = ({
  isOpen,
  onClose,
  student,
  onSuccess,
}) => {
  const [targetGroupId, setTargetGroupId] = useState<string>("");
  const [sourceGroupId, setSourceGroupId] = useState("");
  const [reason, setReason] = useState("");
  const [search, setSearch] = useState("");
  const [groups, setGroups] = useState<StudentGroupOption[]>([]);
  const [isLoadingGroups, setIsLoadingGroups] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && student) {
      const active = studentEnrollments(student).filter(item => item.is_active);
      setSourceGroupId(active.some(item => item.group.id === student.group_id) ? student.group_id : active[0]?.group.id ?? "");
      setReason(""); setSearch("");
    }
  }, [isOpen, student]);

  useEffect(() => {
    if (!isOpen || !student) return;
    let cancelled = false;
    const loadGroups = async () => {
      setIsLoadingGroups(true);
      setError(null);
      try {
        const res = await apiClient.get<{ items: StudentGroupOption[] }>("/api/v1/admin/lookups/student-groups");
        if (cancelled) return;
        const available = res.items.filter((g) => g.id !== sourceGroupId);
        setGroups(available);
        if (available.length > 0) {
          setTargetGroupId(available[0].id);
        } else {
          setTargetGroupId("");
        }
      } catch {
        if (!cancelled) setError("Guruhlar ro‘yxatini yuklashda xatolik yuz berdi");
      } finally {
        if (!cancelled) setIsLoadingGroups(false);
      }
    };

    loadGroups();
    return () => { cancelled = true; };
  }, [isOpen, student, sourceGroupId]);

  if (!student) {
    return null;
  }

  const selectedGroup = groups.find((g) => g.id === targetGroupId);
  const isSelectedGroupFull = selectedGroup
    ? selectedGroup.current_students >= selectedGroup.max_students && !studentEnrollments(student).some(item => item.is_active && item.group.id === targetGroupId)
    : false;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) { setError("Ko‘chirish sababini kiriting"); return; }
    if (!sourceGroupId) { setError("Manba guruhni tanlang"); return; }
    if (!targetGroupId) {
      setError("Ko‘chiriladigan yangi guruhni tanlang");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const payload: StudentTransferInput = {
        target_group_id: targetGroupId,
        source_group_id: sourceGroupId,
        reason: reason.trim(),
      };
      const updated = await apiClient.post<StudentDetailItem>(
        `/api/v1/admin/students/${student.id}/transfer`,
        payload
      );
      onSuccess(updated);
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("O‘quvchini yangi guruhga ko‘chirishda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="O‘quvchini boshqa guruhga ko‘chirish"
      description={`${student.first_name} ${student.last_name ?? ""} ni boshqa guruhga o‘tkazish`}
      size="md"
    >
      {error && (
        <Alert variant="danger" className="mb-4" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
          <div className="text-slate-500 font-medium">Joriy guruh:</div>
          <div className="text-slate-900 font-semibold text-sm">{studentEnrollments(student).find(item => item.group.id === sourceGroupId)?.group.name ?? student.group.name}</div>
          <p>Boshqa kurslar, ota-ona va oldingi davomat tarixi saqlanadi.</p>
        </div>

        <Select label="Qaysi guruhdan ko‘chirish" value={sourceGroupId} onChange={event => setSourceGroupId(event.target.value)} disabled={isLoading}
          options={studentEnrollments(student).filter(item => item.is_active).map(item => ({ value: item.group.id, label: item.group.name }))} />
        <Input label="Yangi guruhdan qidirish" value={search} onChange={event => { setSearch(event.target.value); setTargetGroupId(""); }} disabled={isLoading} />

        <Select
          label="Yangi guruhni tanlang"
          required
          value={targetGroupId}
          onChange={(e) => setTargetGroupId(e.target.value)}
          disabled={isLoading || isLoadingGroups}
          options={[
            { value: "", label: "-- Guruhni tanlang --" },
            ...groups.filter(g => g.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map((g) => {
              const full = g.current_students >= g.max_students;
              return {
                value: g.id,
                label: `${g.name} (${g.current_students}/${g.max_students} o‘quvchi)${
                  full ? " — [TO‘LGAN]" : ""
                }`,
              };
            }),
          ]}
          helperText="Faqat faol va joriy guruhdan farqli guruhlar ko‘rsatilgan"
        />
        <Input label="Ko‘chirish sababi" required maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} disabled={isLoading} />

        {isSelectedGroupFull && (
          <Alert variant="warning">
            Diqqat: Tanlangan guruh allaqachon maksimal sig‘imga yetgan. Tizim ko‘chirishni rad etishi mumkin.
          </Alert>
        )}

        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
          <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
            Bekor qilish
          </Button>
          <Button
            type="submit"
            variant="primary"
            isLoading={isLoading}
            leftIcon={<ArrowRightLeft className="w-4 h-4" />}
          >
            Guruhga ko‘chirish
          </Button>
        </div>
      </form>
    </Modal>
  );
};
