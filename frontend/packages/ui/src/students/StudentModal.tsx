import React, { useState, useEffect } from "react";
import type { StudentItem, StudentDetailItem, StudentCreateInput, StudentUpdateInput } from "./types";
import type { GroupItem } from "../academic/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Modal } from "../components/Modal";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { User, Users } from "lucide-react";

export interface StudentModalProps {
  isOpen: boolean;
  onClose: () => void;
  student: StudentItem | null;
  onSuccess: (saved: StudentDetailItem) => void;
  initialGroupId?: string;
}

export const StudentModal: React.FC<StudentModalProps> = ({
  isOpen,
  onClose,
  student,
  onSuccess,
  initialGroupId,
}) => {
  const isEditing = Boolean(student);

  // Student fields
  const [firstName, setFirstName] = useState<string>("");
  const [lastName, setLastName] = useState<string>("");
  const [phone, setPhone] = useState<string>("");
  const [age, setAge] = useState<string>("16");
  const [groupId, setGroupId] = useState<string>("");

  // Parent fields
  const [parentFirstName, setParentFirstName] = useState<string>("");
  const [parentLastName, setParentLastName] = useState<string>("");
  const [parentPhone, setParentPhone] = useState<string>("");

  // Group options
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [isLoadingGroups, setIsLoadingGroups] = useState<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load active groups for dropdown
  useEffect(() => {
    if (!isOpen || isEditing) return;

    const loadGroups = async () => {
      setIsLoadingGroups(true);
      try {
        const res = await apiClient.get<{ items: GroupItem[] }>("/api/v1/admin/groups", {
          params: { page_size: 100, status: "active" },
        });
        setGroups(res.items);
        if (initialGroupId) {
          setGroupId(initialGroupId);
        } else if (res.items.length > 0 && !groupId) {
          setGroupId(res.items[0].id);
        }
      } catch {
        // Fallback
      } finally {
        setIsLoadingGroups(false);
      }
    };

    loadGroups();
  }, [isOpen, isEditing, initialGroupId]);

  useEffect(() => {
    if (student) {
      setFirstName(student.first_name);
      setLastName(student.last_name);
      setPhone(student.phone);
      setAge(String(student.age));
      setGroupId(student.group_id);

      setParentFirstName(student.parent.first_name);
      setParentLastName(student.parent.last_name);
      setParentPhone(student.parent.phone);
    } else {
      setFirstName("");
      setLastName("");
      setPhone("+998");
      setAge("16");
      setGroupId(initialGroupId || "");

      setParentFirstName("");
      setParentLastName("");
      setParentPhone("+998");
    }
    setError(null);
  }, [student, isOpen, initialGroupId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!firstName.trim() || !lastName.trim()) {
      setError("Talaba ism va familiyasini kiriting");
      return;
    }
    if (!/^\+[1-9][0-9]{7,14}$/.test(phone.trim())) {
      setError("Talaba telefon raqami formati noto‘g‘ri (masalan: +998901234567)");
      return;
    }
    const ageNum = parseInt(age, 10);
    if (isNaN(ageNum) || ageNum < 3 || ageNum > 100) {
      setError("Talaba yoshi 3 va 100 oralig‘ida bo‘lishi kerak");
      return;
    }
    if (!isEditing && !groupId) {
      setError("Guruhni tanlang");
      return;
    }

    // Parent validation
    if (!parentFirstName.trim() || !parentLastName.trim()) {
      setError("Ota-ona ism va familiyasini kiriting");
      return;
    }
    if (!/^\+[1-9][0-9]{7,14}$/.test(parentPhone.trim())) {
      setError("Ota-ona telefon raqami formati noto‘g‘ri (masalan: +998901234567)");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      if (isEditing && student) {
        const payload: StudentUpdateInput = {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          phone: phone.trim(),
          age: ageNum,
          parent: {
            first_name: parentFirstName.trim(),
            last_name: parentLastName.trim(),
            phone: parentPhone.trim(),
          },
        };
        const updated = await apiClient.patch<StudentDetailItem>(
          `/api/v1/admin/students/${student.id}`,
          payload
        );
        onSuccess(updated);
      } else {
        const payload: StudentCreateInput = {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          phone: phone.trim(),
          age: ageNum,
          group_id: groupId,
          parent: {
            first_name: parentFirstName.trim(),
            last_name: parentLastName.trim(),
            phone: parentPhone.trim(),
          },
        };
        const created = await apiClient.post<StudentDetailItem>("/api/v1/admin/students", payload);
        onSuccess(created);
      }
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Talabani saqlashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditing ? "Talaba ma’lumotlarini tahrirlash" : "Yangi talaba va ota-onani ro‘yxatga olish"}
      description={
        isEditing
          ? `${student?.first_name} ${student?.last_name} profilini tahrirlash`
          : "Talaba va uning ota-onasini yagona forma orqali tizimga kiritish"
      }
      size="lg"
    >
      {error && (
        <Alert variant="danger" className="mb-4" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-6">
        {/* Student Section */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100 text-slate-800 font-semibold text-sm">
            <User className="w-4 h-4 text-blue-600" />
            <span>Talaba ma’lumotlari</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Ism"
              placeholder="masalan: Jasur"
              required
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              disabled={isLoading}
            />
            <Input
              label="Familiya"
              placeholder="masalan: Bekmurodov"
              required
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Telefon raqami"
              placeholder="+998901234567"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={isLoading}
              helperText="Xalqaro formatda (+998...)"
            />
            <Input
              label="Yoshi"
              type="number"
              min="3"
              max="100"
              required
              value={age}
              onChange={(e) => setAge(e.target.value)}
              disabled={isLoading}
            />
          </div>

          {!isEditing && (
            <Select
              label="Biriktiriladigan guruh"
              required
              value={groupId}
              onChange={(e) => setGroupId(e.target.value)}
              disabled={isLoading || isLoadingGroups}
              options={[
                { value: "", label: "-- Guruhni tanlang --" },
                ...groups.map((g) => {
                  const isFull = g.current_students >= g.max_students;
                  return {
                    value: g.id,
                    label: `${g.name} (${g.current_students}/${g.max_students} talaba)${
                      isFull ? " — [TO‘LGAN]" : ""
                    }`,
                  };
                }),
              ]}
              helperText="Guruh sig‘imi to‘lgan bo‘lsa, tizim ro‘yxatga olishni rad etadi"
            />
          )}
        </div>

        {/* Parent Section */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100 text-slate-800 font-semibold text-sm">
            <Users className="w-4 h-4 text-indigo-600" />
            <span>Ota-ona ma’lumotlari</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Ota-ona ismi"
              placeholder="masalan: Otabek"
              required
              value={parentFirstName}
              onChange={(e) => setParentFirstName(e.target.value)}
              disabled={isLoading}
            />
            <Input
              label="Ota-ona familiyasi"
              placeholder="masalan: Bekmurodov"
              required
              value={parentLastName}
              onChange={(e) => setParentLastName(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <Input
            label="Ota-ona telefon raqami"
            placeholder="+998909876543"
            required
            value={parentPhone}
            onChange={(e) => setParentPhone(e.target.value)}
            disabled={isLoading}
            helperText="Telegram bot bildirishnomalari ushbu raqamga bog‘lanadi"
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
          <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
            Bekor qilish
          </Button>
          <Button type="submit" variant="primary" isLoading={isLoading}>
            {isEditing ? "Saqlash" : "Ro‘yxatga olish"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
