import { useEffect, useState } from "react";
import { Layers, Plus, X } from "lucide-react";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { formatDaysOfWeek, formatPrice } from "../academic/types";
import type { StudentGroupOption } from "../academic/types";
import { Alert } from "../components/Alert";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Select } from "../components/Select";
import { studentEnrollments } from "./types";
import { StudentCourseMetadata } from "../components/StudentCourseMetadata";
import { EnrollmentMetadataEditor } from "./EnrollmentMetadataEditor";
import type { StudentDetailItem } from "./types";

export function StudentGroupsPanel({ student, canEdit, onUpdated }: {
  student: StudentDetailItem; canEdit: boolean; onUpdated: (student: StudentDetailItem) => void;
}) {
  const [options, setOptions] = useState<StudentGroupOption[]>([]);
  const [target, setTarget] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const enrollments = studentEnrollments(student);
  const active = enrollments.filter((item) => item.is_active);
  const available = options.filter((item) => !active.some((row) => row.group.id === item.id));

  useEffect(() => {
    if (!canEdit) return;
    let current = true;
    apiClient.get<{ items: StudentGroupOption[] }>("/api/v1/admin/lookups/student-groups")
      .then((data) => { if (current) setOptions(data.items ?? []); })
      .catch(() => { if (current) setError("Guruhlar ro‘yxati yuklanmadi. Profilni qayta oching."); });
    return () => { current = false; };
  }, [canEdit, student.id]);

  async function save(groupId: string, isActive: boolean) {
    if (!canEdit || busy || !groupId) return;
    setBusy(true); setError(null);
    try {
      const updated = await apiClient.put<StudentDetailItem>(
        `/api/v1/admin/students/${student.id}/groups/${groupId}`, { is_active: isActive },
      );
      onUpdated(updated); setTarget(""); setRemoving(null);
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.detail : "Biriktirish saqlanmadi. Qayta urinib ko‘ring.");
    } finally { setBusy(false); }
  }

  return <section aria-label="O‘quvchi guruhlari" className="rounded-xl border border-slate-200 p-4 space-y-3">
    <h3 className="flex items-center gap-2 text-sm font-semibold"><Layers className="size-4 text-blue-600" />Guruh va dars tafsilotlari</h3>
    <p className="text-xs text-slate-500">Bitta profil bir nechta kursda o‘qishi mumkin. Har bir guruhning davomati alohida.</p>
    {error && <Alert variant="danger">{error}</Alert>}
    {enrollments.map((enrollment) => { const { group, is_active } = enrollment; return <article key={group.id} className="rounded-lg border border-slate-200 p-3 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <strong className="text-sm break-words">{group.name}</strong>
        <Badge variant={is_active ? "success" : "neutral"}>{is_active ? "Biriktirilgan" : "Oldingi guruh"}</Badge>
      </div>
      <dl className="grid gap-2 text-xs sm:grid-cols-3">
        {[
          ["Fan", group.subject_name], ["O‘qituvchi", group.teacher_name],
          ["Oylik to‘lov", formatPrice(group.monthly_price)],
          ["Dars kunlari", formatDaysOfWeek(group.days_of_week ?? [])],
          ["Dars vaqti", `${group.start_time?.slice(0, 5) ?? "—"} – ${group.end_time?.slice(0, 5) ?? "—"}`],
          ["Xona", group.room_number],
        ].map(([label, value]) => <div key={label} className="rounded-md bg-slate-50 p-2 min-w-0">
          <dt className="text-slate-500">{label}</dt><dd className="font-medium break-words">{value || "—"}</dd>
        </div>)}
      </dl>
      <StudentCourseMetadata {...enrollment} />
      {canEdit && (editing === group.id ? <EnrollmentMetadataEditor studentId={student.id} enrollment={enrollment}
        onSaved={onUpdated} onClose={() => setEditing(null)} /> :
        <Button size="sm" variant="outline" disabled={busy} onClick={() => setEditing(group.id)}>Kurs ma’lumotlarini tahrirlash</Button>)}
      {canEdit && is_active && (removing === group.id ? <div className="space-y-2">
        <p className="text-xs">Bu guruhdan biriktirish olinsinmi? Oldingi davomat tarixi saqlanadi. Boshqa kurslarga ta’sir qilmaydi.</p>
        <div className="flex flex-wrap gap-2"><Button size="sm" variant="danger" isLoading={busy} onClick={() => save(group.id, false)}>Biriktirishni olish</Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => setRemoving(null)}>Bekor qilish</Button></div>
      </div> : <Button size="sm" variant="ghost" disabled={busy} leftIcon={<X className="size-3" />} onClick={() => setRemoving(group.id)}>Guruhdan olish</Button>)}
    </article>; })}
    {!enrollments.length && <p className="text-sm text-slate-500">Guruhga biriktirilmagan</p>}
    {canEdit && <div className="space-y-2">
      <Select label="Qo‘shimcha guruh" value={target} disabled={busy} onChange={(event) => setTarget(event.target.value)}>
        <option value="">Guruhni tanlang</option>
        {available.map((item) => <option key={item.id} value={item.id} disabled={student.status === "active" && item.current_students >= item.max_students}>
          {item.name} ({item.current_students}/{item.max_students})
        </option>)}
      </Select>
      <Button size="sm" disabled={!target || busy} isLoading={busy} leftIcon={<Plus className="size-4" />} onClick={() => save(target, true)}>Guruhga biriktirish</Button>
    </div>}
  </section>;
}
