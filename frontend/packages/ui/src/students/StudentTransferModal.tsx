import React, { useState, useEffect } from "react";
import type { StudentItem, StudentDetailItem, StudentTransferInput } from "./types";
import type { GroupItem } from "../academic/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Modal } from "../components/Modal";
import { Select } from "../components/Select";
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
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [isLoadingGroups, setIsLoadingGroups] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !student) return;

    const loadGroups = async () => {
      setIsLoadingGroups(true);
      setError(null);
      try {
        const res = await apiClient.get<{ items: GroupItem[] }>("/api/v1/admin/groups", {
          params: { page_size: 100, status: "active" },
        });
        // Filter out current group
        const available = res.items.filter((g) => g.id !== student.group_id);
        setGroups(available);
        if (available.length > 0) {
          setTargetGroupId(available[0].id);
        } else {
          setTargetGroupId("");
        }
      } catch {
        setError("Guruhlar ro‘yxatini yuklashda xatolik yuz berdi");
      } finally {
        setIsLoadingGroups(false);
      }
    };

    loadGroups();
  }, [isOpen, student]);

  if (!student) {
    return null;
  }

  const selectedGroup = groups.find((g) => g.id === targetGroupId);
  const isSelectedGroupFull = selectedGroup
    ? selectedGroup.current_students >= selectedGroup.max_students
    : false;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetGroupId) {
      setError("Ko‘chiriladigan yangi guruhni tanlang");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const payload: StudentTransferInput = {
        target_group_id: targetGroupId,
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
        setError("Talabani yangi guruhga ko‘chirishda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Talabani boshqa guruhga ko‘chirish"
      description={`${student.first_name} ${student.last_name} ni boshqa guruhga o‘tkazish`}
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
          <div className="text-slate-900 font-semibold text-sm">{student.group.name}</div>
        </div>

        <Select
          label="Yangi guruhni tanlang"
          required
          value={targetGroupId}
          onChange={(e) => setTargetGroupId(e.target.value)}
          disabled={isLoading || isLoadingGroups}
          options={[
            { value: "", label: "-- Guruhni tanlang --" },
            ...groups.map((g) => {
              const full = g.current_students >= g.max_students;
              return {
                value: g.id,
                label: `${g.name} (${g.current_students}/${g.max_students} talaba)${
                  full ? " — [TO‘LGAN]" : ""
                }`,
              };
            }),
          ]}
          helperText="Faqat faol va joriy guruhdan farqli guruhlar ko‘rsatilgan"
        />

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
