import React, { useState, useEffect } from "react";
import type { SubjectItem, SubjectCreateInput, SubjectUpdateInput } from "./types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Modal } from "../components/Modal";
import { Input } from "../components/Input";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";

export interface SubjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  subject: SubjectItem | null;
  onSuccess: (saved: SubjectItem) => void;
}

export const SubjectModal: React.FC<SubjectModalProps> = ({
  isOpen,
  onClose,
  subject,
  onSuccess,
}) => {
  const isEditing = Boolean(subject);
  const [name, setName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (subject) {
      setName(subject.name);
      setDescription(subject.description || "");
    } else {
      setName("");
      setDescription("");
    }
    setError(null);
  }, [subject, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Fan nomini kiriting");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      if (isEditing && subject) {
        const payload: SubjectUpdateInput = {
          name: name.trim(),
          description: description.trim() || null,
        };
        const updated = await apiClient.patch<SubjectItem>(
          `/api/v1/admin/subjects/${subject.id}`,
          payload
        );
        onSuccess(updated);
      } else {
        const payload: SubjectCreateInput = {
          name: name.trim(),
          description: description.trim() || null,
        };
        const created = await apiClient.post<SubjectItem>("/api/v1/admin/subjects", payload);
        onSuccess(created);
      }
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Fanni saqlashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditing ? "Fanni tahrirlash" : "Yangi fan qo‘shish"}
      description={
        isEditing
          ? `"${subject?.name}" fani ma’lumotlarini tahrirlash`
          : "O‘quv markazi uchun yangi fan va kurs yo‘nalishini yaratish"
      }
      size="md"
    >
      {error && (
        <Alert variant="danger" className="mb-4" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <Input
          label="Fan nomi"
          placeholder="masalan: Dasturlash asoslari (Python)"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isLoading}
        />

        <div className="w-full">
          <label htmlFor="subject-description" className="block text-sm font-medium text-slate-700 mb-1">
            Tavsif (ixtiyoriy)
          </label>
          <textarea
            id="subject-description"
            rows={3}
            placeholder="Fan haqida qisqacha ma’lumot va maqsadlar..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isLoading}
            className="block w-full rounded-lg border border-slate-300 text-sm p-3 transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200 disabled:bg-slate-50 disabled:text-slate-500"
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
