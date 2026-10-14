import { useCallback, useEffect, useState, type FormEvent } from "react";
import { DoorOpen, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import type { CurrentUser } from "../api/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { hasPermission, PERMISSIONS } from "../navigation/permissions";
import { formatDateTime } from "../lib/dates";
import { Alert } from "../components/Alert";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { LoadingState } from "../components/LoadingState";
import { Modal } from "../components/Modal";
import { Select } from "../components/Select";
import type { RoomItem } from "./types";

export function RoomsManagementView({ currentUser }: { currentUser: CurrentUser }) {
  const allowed = hasPermission(currentUser, PERMISSIONS.ROOMS_MANAGE);
  const [rooms, setRooms] = useState<RoomItem[]>([]), [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null), [busy, setBusy] = useState(false);
  const [search, setSearch] = useState(""), [status, setStatus] = useState("all");
  const [mode, setMode] = useState<"create" | "edit" | "delete" | null>(null);
  const [selected, setSelected] = useState<RoomItem | null>(null);
  const [name, setName] = useState(""), [description, setDescription] = useState("");
  const load = useCallback(async () => {
    if (!allowed) return;
    setLoading(true); setError(null);
    try { setRooms(await apiClient.get<RoomItem[]>("/api/v1/admin/rooms")); }
    catch (failure) { setError(failure instanceof ApiError ? failure.detail : "Xonalar yuklanmadi"); }
    finally { setLoading(false); }
  }, [allowed]);
  useEffect(() => { void load(); }, [load]);
  function open(next: "create" | "edit" | "delete", room: RoomItem | null = null) {
    setSelected(room); setName(room?.name ?? ""); setDescription(room?.description ?? ""); setError(null); setMode(next);
  }
  async function change(action: () => Promise<unknown>, close = false) {
    if (!allowed || busy) return;
    setBusy(true); setError(null);
    try { await action(); if (close) setMode(null); await load(); }
    catch (failure) { setError(failure instanceof ApiError ? failure.detail : "Xona saqlanmadi"); }
    finally { setBusy(false); }
  }
  function save(event: FormEvent) {
    event.preventDefault();
    if (mode === "delete" && selected) return change(() => apiClient.delete(`/api/v1/admin/rooms/${selected.id}`), true);
    if (!name.trim()) { setError("Xona nomi yoki raqamini kiriting"); return; }
    const body = { name: name.trim(), description: description.trim() || null };
    return change(() => selected ? apiClient.patch(`/api/v1/admin/rooms/${selected.id}`, body) : apiClient.post("/api/v1/admin/rooms", body), true);
  }
  if (!allowed) return <Alert variant="danger">Xonalarni boshqarish uchun ruxsat yo‘q.</Alert>;
  const filtered = rooms.filter(room => (!search || `${room.name} ${room.description ?? ""}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
    && (status === "all" || room.is_active === (status === "active")));
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-bold">Xonalar</h1>
      <p className="text-sm text-slate-500">Dars xonalarini yarating va guruh formasida biriktiring.</p></div>
      <div className="flex gap-2"><Button variant="outline" disabled={busy} onClick={load} leftIcon={<RefreshCw className="size-4" />}>Yangilash</Button>
        <Button onClick={() => open("create")} leftIcon={<Plus className="size-4" />}>Xona qo‘shish</Button></div></div>
    {error && !mode && <Alert variant="danger">{error}</Alert>}
    <Card className="p-4 grid gap-3 sm:grid-cols-2"><Input label="Xonadan qidirish" value={search} onChange={event => setSearch(event.target.value)} />
      <Select label="Xona holati" value={status} onChange={event => setStatus(event.target.value)} options={[{ value: "all", label: "Barchasi" }, { value: "active", label: "Faol" }, { value: "inactive", label: "Faol emas" }]} /></Card>
    {loading ? <LoadingState message="Xonalar yuklanmoqda..." /> : <div className="space-y-3">
      {!filtered.length && <Card className="p-6 text-sm text-slate-500">Xona topilmadi. Yangi xona qo‘shing yoki filtrni o‘zgartiring.</Card>}
      {filtered.map(room => <Card key={room.id} className="p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-1"><h2 className="flex flex-wrap items-center gap-2 font-semibold"><DoorOpen className="size-4" />{room.name}
          <Badge variant={room.is_active ? "success" : "neutral"}>{room.is_active ? "Faol" : "Faol emas"}</Badge></h2>
          {room.description && <p className="text-sm break-words whitespace-pre-wrap text-slate-600">{room.description}</p>}
          <p className="text-xs text-slate-500">Yangilangan: {formatDateTime(room.updated_at)}</p></div>
        <div className="flex flex-wrap shrink-0 gap-2"><Button size="sm" variant="outline" disabled={busy} onClick={() => open("edit", room)} leftIcon={<Pencil className="size-3" />}>Tahrirlash</Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => change(() => apiClient.patch(`/api/v1/admin/rooms/${room.id}`, { is_active: !room.is_active }))}>{room.is_active ? "Faolsizlantirish" : "Faollashtirish"}</Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => open("delete", room)} aria-label={`${room.name} xonani o‘chirish`}><Trash2 className="size-4" /></Button></div>
      </Card>)}
    </div>}
    <Modal isOpen={mode !== null} onClose={() => { if (!busy) setMode(null); }} title={mode === "delete" ? "Xonani o‘chirish" : selected ? "Xonani tahrirlash" : "Xona qo‘shish"} size="md">
      <form onSubmit={save} className="space-y-4">
        {error && <Alert variant="danger">{error}</Alert>}
        {mode === "delete" ? <p className="text-sm">{selected?.name} xonasi o‘chirilsinmi? Guruh biriktirilgan xona serverda o‘chirilmaydi.</p> : <>
          <Input label="Xona nomi / raqami" required maxLength={30} disabled={busy} value={name} onChange={event => setName(event.target.value)} />
          <label className="block text-sm font-medium" htmlFor="room-description">Xona izohi</label>
          <textarea id="room-description" rows={3} maxLength={1000} disabled={busy} value={description} onChange={event => setDescription(event.target.value)} className="w-full rounded-lg border border-slate-300 p-2 text-sm" />
        </>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={() => setMode(null)}>Bekor qilish</Button>
          <Button type="submit" variant={mode === "delete" ? "danger" : "primary"} isLoading={busy}>{mode === "delete" ? "O‘chirishni tasdiqlash" : "Saqlash"}</Button></div>
      </form>
    </Modal>
  </div>;
}
