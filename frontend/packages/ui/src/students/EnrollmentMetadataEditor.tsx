import { useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import type { StudentDetailItem, StudentEnrollment } from "./types";

export function EnrollmentMetadataEditor({ studentId, enrollment, onSaved, onClose }: {
  studentId: string; enrollment: StudentEnrollment;
  onSaved: (student: StudentDetailItem) => void; onClose: () => void;
}) {
  const [level, setLevel] = useState(enrollment.level ?? "");
  const [mygov, setMygov] = useState(enrollment.mygov_status ?? "");
  const [notes, setNotes] = useState(enrollment.notes ?? "");
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  async function save(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError(null);
    try {
      const updated = await apiClient.patch<StudentDetailItem>(
        `/api/v1/admin/students/${studentId}/groups/${enrollment.group.id}`,
        { level: level.trim() || null, mygov_status: mygov.trim() || null, notes: notes.trim() || null },
      );
      onSaved(updated); onClose();
    } catch (failure) { setError(failure instanceof ApiError ? failure.detail : "Kurs ma’lumotlari saqlanmadi"); }
    finally { setBusy(false); }
  }
  return <form aria-label={`${enrollment.group.name} kurs ma’lumotlari`} onSubmit={save} className="space-y-2">
    {error && <Alert variant="danger">{error}</Alert>}
    <Input label="Daraja" maxLength={150} value={level} disabled={busy} onChange={(event) => setLevel(event.target.value)} />
    <Input label="MyGov holati" maxLength={150} value={mygov} disabled={busy} onChange={(event) => setMygov(event.target.value)} helperText="Masalan: o‘tdi, o‘tmadi, reyestrda yo‘q. Login yoki parol yozmang." />
    <label htmlFor={`course-notes-${enrollment.group.id}`} className="block text-sm font-medium">Kurs izohi</label>
    <textarea id={`course-notes-${enrollment.group.id}`} maxLength={4000} rows={3} value={notes} disabled={busy}
      onChange={(event) => setNotes(event.target.value)} className="w-full rounded-lg border border-slate-300 p-2 text-sm" />
    <div className="flex flex-wrap gap-2"><Button size="sm" type="submit" isLoading={busy}>Kurs ma’lumotlarini saqlash</Button>
      <Button size="sm" type="button" variant="outline" disabled={busy} onClick={onClose}>Bekor qilish</Button></div>
  </form>;
}
