import React, { useState, useEffect } from "react";
import type { GroupItem, GroupCreateInput, GroupUpdateInput, SubjectItem } from "./types";
import type { StaffItem } from "../staff/types";
import { DAYS_OF_WEEK } from "./types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Modal } from "../components/Modal";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";

export interface GroupModalProps {
  isOpen: boolean;
  onClose: () => void;
  group: GroupItem | null;
  onSuccess: (saved: GroupItem) => void;
}

export const GroupModal: React.FC<GroupModalProps> = ({
  isOpen,
  onClose,
  group,
  onSuccess,
}) => {
  const isEditing = Boolean(group);

  const [name, setName] = useState<string>("");
  const [subjectId, setSubjectId] = useState<string>("");
  const [teacherId, setTeacherId] = useState<string>("");
  const [daysOfWeek, setDaysOfWeek] = useState<number[]>([]);
  const [startTime, setStartTime] = useState<string>("09:00");
  const [endTime, setEndTime] = useState<string>("11:00");
  const [roomNumber, setRoomNumber] = useState<string>("");
  const [monthlyPrice, setMonthlyPrice] = useState<string>("500000");
  const [maxStudents, setMaxStudents] = useState<string>("15");

  // Options from API
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [teachers, setTeachers] = useState<StaffItem[]>([]);
  const [isLoadingOptions, setIsLoadingOptions] = useState<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load subjects and active teachers for selection
  useEffect(() => {
    if (!isOpen) return;

    const loadOptions = async () => {
      setIsLoadingOptions(true);
      try {
        const [subRes, staffRes] = await Promise.all([
          apiClient.get<{ items: SubjectItem[] }>("/api/v1/admin/subjects", {
            params: { page_size: 100, is_active: true },
          }),
          apiClient.get<{ items: StaffItem[] }>("/api/v1/admin/staff", {
            params: { page_size: 100, role: "teacher", status: "active" },
          }),
        ]);
        setSubjects(subRes.items);
        setTeachers(staffRes.items);

        // Set defaults if creating and not set
        if (!group) {
          if (subRes.items.length > 0 && !subjectId) {
            setSubjectId(subRes.items[0].id);
          }
          if (staffRes.items.length > 0 && !teacherId) {
            setTeacherId(staffRes.items[0].id);
          }
        }
      } catch {
        // Fallback or alert if options fail
      } finally {
        setIsLoadingOptions(false);
      }
    };

    loadOptions();
  }, [isOpen, group]);

  useEffect(() => {
    if (group) {
      setName(group.name);
      setSubjectId(group.subject_id);
      setTeacherId(group.teacher_id);
      setDaysOfWeek(group.days_of_week || []);
      // Format time strings (HH:MM:SS -> HH:MM)
      setStartTime(group.start_time?.slice(0, 5) ?? "");
      setEndTime(group.end_time?.slice(0, 5) ?? "");
      setRoomNumber(group.room_number ?? "");
      setMonthlyPrice(group.monthly_price == null ? "" : String(group.monthly_price));
      setMaxStudents(String(group.max_students));
    } else {
      setName("");
      setDaysOfWeek([1, 3, 5]); // Default: Mon, Wed, Fri
      setStartTime("09:00");
      setEndTime("11:00");
      setRoomNumber("");
      setMonthlyPrice("500000");
      setMaxStudents("15");
    }
    setError(null);
  }, [group, isOpen]);

  const toggleDay = (dayValue: number) => {
    setDaysOfWeek((prev) =>
      prev.includes(dayValue) ? prev.filter((d) => d !== dayValue) : [...prev, dayValue].sort((a, b) => a - b)
    );
  };

  const applyPresetDays = (preset: number[]) => {
    setDaysOfWeek(preset);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      setError("Guruh nomini kiriting");
      return;
    }
    if (!subjectId) {
      setError("Fanni tanlang");
      return;
    }
    if (!teacherId) {
      setError("O‘qituvchini tanlang");
      return;
    }
    if (daysOfWeek.length === 0) {
      setError("Kamida bitta dars kuni tanlanishi kerak");
      return;
    }
    if (startTime && endTime && startTime >= endTime) {
      setError("Dars boshlanish vaqti tugash vaqtidan oldin bo‘lishi kerak");
      return;
    }
    const priceNum = parseFloat(monthlyPrice);
    if (monthlyPrice.trim() && (isNaN(priceNum) || priceNum < 0)) {
      setError("Oylik to‘lov summasi noto‘g‘ri kiritildi");
      return;
    }

    const maxStudentsNum = parseInt(maxStudents, 10);
    if (isNaN(maxStudentsNum) || maxStudentsNum < 1) {
      setError("Maksimal o‘quvchilar soni kamida 1 bo‘lishi kerak");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      if (isEditing && group) {
        const payload: GroupUpdateInput = {
          name: name.trim(),
          subject_id: subjectId,
          teacher_id: teacherId,
          monthly_price: monthlyPrice.trim() ? priceNum : undefined,
          max_students: maxStudentsNum,
          days_of_week: daysOfWeek,
          start_time: startTime || undefined,
          end_time: endTime || undefined,
          room_number: roomNumber.trim() || undefined,
        };
        const updated = await apiClient.patch<GroupItem>(`/api/v1/admin/groups/${group.id}`, payload);
        onSuccess(updated);
      } else {
        const payload: GroupCreateInput = {
          name: name.trim(),
          subject_id: subjectId,
          teacher_id: teacherId,
          monthly_price: monthlyPrice.trim() ? priceNum : null,
          max_students: maxStudentsNum,
          days_of_week: daysOfWeek,
          start_time: startTime || null,
          end_time: endTime || null,
          room_number: roomNumber.trim() || null,
        };
        const created = await apiClient.post<GroupItem>("/api/v1/admin/groups", payload);
        onSuccess(created);
      }
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Guruhni saqlashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditing ? "Guruh ma’lumotlarini tahrirlash" : "Yangi guruh ochish"}
      description={
        isEditing
          ? `"${group?.name}" guruhi jadvali va parametrlarini o‘zgartirish`
          : "Yangi dars jadvali, o‘qituvchi va xonani biriktirish"
      }
      size="lg"
    >
      {error && (
        <Alert variant="danger" className="mb-4" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        {/* Name */}
        <Input
          label="Guruh nomi"
          placeholder="masalan: Python Backend - 1-guruh"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isLoading}
        />

        {/* Subject & Teacher select */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="Fan"
            required
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            disabled={isLoading || isLoadingOptions}
            options={[
              { value: "", label: "-- Fanni tanlang --" },
              ...subjects.map((s) => ({ value: s.id, label: s.name })),
            ]}
          />

          <Select
            label="O‘qituvchi"
            required
            value={teacherId}
            onChange={(e) => setTeacherId(e.target.value)}
            disabled={isLoading || isLoadingOptions}
            options={[
              { value: "", label: "-- O‘qituvchini tanlang --" },
              ...teachers.map((t) => ({
                value: t.id,
                label: `${t.first_name} ${t.last_name ?? ""} (${t.phone ?? "Telefon kiritilmagan"})`,
              })),
            ]}
          />
        </div>

        {/* Days of week */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="block text-sm font-medium text-slate-700">
              Dars kunlari <span className="text-red-500">*</span>
            </label>
            <div className="flex items-center gap-1.5 text-xs">
              <button
                type="button"
                onClick={() => applyPresetDays([1, 3, 5])}
                className="text-blue-600 hover:text-blue-800 font-medium px-1.5 py-0.5 rounded hover:bg-blue-50"
              >
                Toq kunlar
              </button>
              <span className="text-slate-300">|</span>
              <button
                type="button"
                onClick={() => applyPresetDays([2, 4, 6])}
                className="text-blue-600 hover:text-blue-800 font-medium px-1.5 py-0.5 rounded hover:bg-blue-50"
              >
                Juft kunlar
              </button>
              <span className="text-slate-300">|</span>
              <button
                type="button"
                onClick={() => applyPresetDays([1, 2, 3, 4, 5, 6])}
                className="text-blue-600 hover:text-blue-800 font-medium px-1.5 py-0.5 rounded hover:bg-blue-50"
              >
                Har kuni
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-slate-50 p-3 rounded-lg border border-slate-200">
            {DAYS_OF_WEEK.map((day) => (
              <label
                key={day.value}
                className="flex items-center gap-2 text-xs text-slate-800 cursor-pointer select-none"
              >
                <input
                  type="checkbox"
                  checked={daysOfWeek.includes(day.value)}
                  onChange={() => toggleDay(day.value)}
                  disabled={isLoading}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <span>{day.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Start time & End time */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Dars boshlanish vaqti"
            type="time"
                        value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            disabled={isLoading}
          />
          <Input
            label="Dars tugash vaqti"
            type="time"
                        value={endTime}
            onChange={(e) => setEndTime(e.target.value)}
            disabled={isLoading}
          />
        </div>

        {/* Room, Price & Max students */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Input
            label="Xona raqami / nomi"
            placeholder="masalan: 302-xona"
                        value={roomNumber}
            onChange={(e) => setRoomNumber(e.target.value)}
            disabled={isLoading}
          />
          <Input
            label="Oylik to‘lov (so‘m)"
            type="number"
            min="0"
            step="10000"
                        value={monthlyPrice}
            onChange={(e) => setMonthlyPrice(e.target.value)}
            disabled={isLoading}
          />
          <Input
            label="Sig‘im (maksimal o‘quvchi)"
            type="number"
            min="1"
            max="1000"
            required
            value={maxStudents}
            onChange={(e) => setMaxStudents(e.target.value)}
            disabled={isLoading}
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
          <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
            Bekor qilish
          </Button>
          <Button type="submit" variant="primary" isLoading={isLoading}>
            {isEditing ? "Saqlash" : "Yaratish"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
