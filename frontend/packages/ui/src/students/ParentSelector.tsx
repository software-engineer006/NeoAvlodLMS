import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Alert } from "../components/Alert";
import type { ParentItem } from "./types";
type ParentOption = Pick<ParentItem, "id" | "first_name" | "last_name" | "phone" | "telegram_connected" | "child_count">;

export function ParentSelector({ value, onChange, current, disabled = false }: {
  value: string; onChange: (id: string) => void; current?: ParentItem | null; disabled?: boolean;
}) {
  const [query, setQuery] = useState(""), [rows, setRows] = useState<ParentOption[]>([]);
  const [error, setError] = useState(false), [loading, setLoading] = useState(false);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      if (active) { setLoading(true); setError(false); }
      try {
        const data = await apiClient.get<{ items: ParentOption[] }>("/api/v1/admin/lookups/parents", { params: { q: query.trim() } });
        if (active) setRows(data.items);
      } catch { if (active) setError(true); }
      finally { if (active) setLoading(false); }
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [query]);
  const options = current && !rows.some(row => row.id === current.id) ? [current, ...rows] : rows;
  const chosen = options.find(row => row.id === value);
  return <div className="space-y-2">
    {error && <Alert variant="danger">Ota-onalar yuklanmadi. Qidirishni yangilang.</Alert>}
    <Input label="Ota-onadan qidirish" value={query} disabled={disabled} onChange={event => setQuery(event.target.value)} placeholder="Ism yoki telefon" />
    <Select label="Mavjud ota-ona" value={value} disabled={disabled || loading} onChange={event => onChange(event.target.value)}>
      <option value="">Ota-onani tanlang</option>
      {options.map(row => <option key={row.id} value={row.id}>{row.first_name} {row.last_name} · {row.phone}</option>)}
    </Select>
    {chosen && <p className="text-xs text-slate-500">Telegram: {chosen.telegram_connected ? "ulangan" : "ulanmagan"}.
      {chosen.child_count != null && ` Bog‘langan bolalar: ${chosen.child_count}.`} Barcha bolalar uchun bitta ota-ona profili va Telegram ishlatiladi.</p>}
  </div>;
}
