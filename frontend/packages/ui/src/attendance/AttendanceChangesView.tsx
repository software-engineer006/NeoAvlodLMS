import { formatDateTime } from "../lib/dates";
import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/Table";

export interface AttendanceChange {
  id: string;
  student_name: string;
  actor_name: string;
  actor_role: string;
  action: string;
  old_status: string | null;
  new_status: string;
  old_note: string | null;
  new_note: string | null;
  reason: string | null;
  changed_at: string;
}
const labels: Record<string, string> = {
  present: "Keldi", absent: "Kelmadi", late: "Kech qoldi", draft: "Belgilash",
  finalize: "Yakunlash", correct: "Tuzatish", teacher: "O‘qituvchi",
  admin: "Administrator", superadmin: "Superadmin",
};

export function AttendanceChangesView({ endpoint, revision }: { endpoint: string; revision: number }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<{ items: AttendanceChange[]; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiClient.get<{ items: AttendanceChange[]; total: number }>(endpoint, { params: { page, page_size: 20 } })
      .then((data) => { if (!cancelled) setResult(data); })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : "Tarixni yuklab bo‘lmadi"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [endpoint, revision, page, open]);
  return <div className="space-y-3">
    <Button variant="outline" onClick={() => setOpen(!open)}>{open ? "Tarixni yopish" : "O‘zgarishlar tarixi"}</Button>
    {open && <>
      {error && <Alert variant="danger">{error}</Alert>}
      {loading ? <p>Tarix yuklanmoqda...</p> : result && <>
        {result.total === 0 ? <p className="text-sm text-slate-500">Ushbu dars uchun o‘zgarishlar hali qayd etilmagan.</p> : <Table>
          <TableHeader><TableRow><TableHead>Vaqt</TableHead><TableHead>Bajaruvchi</TableHead><TableHead>O‘quvchi</TableHead><TableHead>Amal</TableHead><TableHead>Oldingi holat / izoh</TableHead><TableHead>Yangi holat / izoh</TableHead><TableHead>Sabab</TableHead></TableRow></TableHeader>
          <TableBody>{result.items.map((item) => <TableRow key={item.id}>
            <TableCell>{formatDateTime(item.changed_at)}</TableCell>
            <TableCell>{item.actor_name}<div className="text-xs text-slate-500">{labels[item.actor_role] || item.actor_role}</div></TableCell>
            <TableCell>{item.student_name}</TableCell><TableCell>{labels[item.action] || item.action}</TableCell>
            <TableCell>{item.old_status ? labels[item.old_status] : "Belgilanmagan"}<div className="whitespace-pre-wrap break-words">{item.old_note || "—"}</div></TableCell>
            <TableCell>{labels[item.new_status]}<div className="whitespace-pre-wrap break-words">{item.new_note || "—"}</div></TableCell>
            <TableCell className="whitespace-pre-wrap break-words">{item.reason || "—"}</TableCell>
          </TableRow>)}</TableBody>
        </Table>}
        {result.total > 20 && <div className="flex gap-3 items-center"><Button disabled={page === 1} onClick={() => setPage(page - 1)}>Oldingi</Button><span>{page} / {Math.ceil(result.total / 20)}</span><Button disabled={page * 20 >= result.total} onClick={() => setPage(page + 1)}>Keyingi</Button></div>}
      </>}
    </>}
  </div>;
}
