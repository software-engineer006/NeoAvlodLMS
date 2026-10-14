import { useEffect, useRef, useState } from "react";
import { Download, RefreshCw, ScrollText } from "lucide-react";
import type { CurrentUser } from "../api/types";
import { apiClient } from "../api/client";
import { canViewLogs } from "../navigation/permissions";
import { ForbiddenPage } from "../navigation/ForbiddenPage";
import { Alert } from "../components/Alert";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/Table";
import { LogDetails } from "./LogDetails";
import { logActionLabel, logDate, logEntityLabel, logEventLabel, logRejected, logTime, logValue } from "./format";
import { useLogPage } from "./useLogPage";
import type { LogDay, LogEvent } from "./types";

const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tashkent",
  year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());

export function LogsView({ currentUser }: { currentUser: CurrentUser }) {
  const allowed = canViewLogs(currentUser);
  const [filters, setFilters] = useState({ day: today(), actor_id: "", action: "", outcome: "", entity: "" });
  const [cursors, setCursors] = useState<string[]>([""]);
  const [revision, setRevision] = useState(0);
  const [days, setDays] = useState<LogDay[]>([]);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ owner: string; entry: LogEvent } | null>(null);
  const downloadController = useRef<AbortController | null>(null);
  useEffect(() => () => downloadController.current?.abort(), [allowed, currentUser.id]);
  const cursor = cursors.at(-1) || "";
  const { data, error, loading } = useLogPage(allowed, currentUser.id, filters, cursor, revision);
  useEffect(() => {
    if (!allowed) return;
    const controller = new AbortController();
    apiClient.get<LogDay[]>("/api/v1/admin/logs/days", { signal: controller.signal })
      .then((rows) => { if (!controller.signal.aborted) setDays(rows); }).catch(() => {});
    return () => controller.abort();
  }, [allowed, currentUser.id, revision]);
  const changeFilter = (key: keyof typeof filters, value: string) => {
    setFilters((previous) => ({ ...previous, [key]: value }));
    setCursors([""]);
    setSelected(null);
  };
  const download = async () => {
    if (!allowed || !filters.day || downloading) return;
    setDownloading(true); setDownloadError(null);
    const controller = new AbortController();
    downloadController.current = controller;
    try {
      const blob = await apiClient.get<Blob>(`/api/v1/admin/logs/${filters.day}/download`, { responseType: "blob", signal: controller.signal });
      if (controller.signal.aborted) return;
      if (blob.type !== "application/gzip") throw new Error("Log fayli formati noto‘g‘ri");
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = `neoavlod-logs-${filters.day}.jsonl.gz`;
      anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      if (!controller.signal.aborted) setDownloadError(error instanceof Error ? error.message : "Loglarni yuklab bo‘lmadi");
    } finally { setDownloading(false); }
  };
  if (!allowed) return <ForbiddenPage />;
  return <div className="space-y-5 max-w-7xl mx-auto">
    <div className="flex flex-col sm:flex-row justify-between gap-3">
      <div><h1 className="text-2xl font-bold text-slate-900">Loglar</h1>
        <p className="text-sm text-slate-500 mt-1">Xodim amallari va o‘zgarishlar. Vaqt: Toshkent, soniyagacha.</p></div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />}
          onClick={() => { setCursors([""]); setRevision((n) => n + 1); }}>Yangilash</Button>
        <Button size="sm" disabled={downloading || !filters.day} onClick={download}
          leftIcon={<Download className="h-4 w-4" />}>{downloading ? "Tayyorlanmoqda…" : "Kunlik logni yuklash"}</Button>
      </div>
    </div>
    <Alert variant="info">Loglar avtomatik saqlanadi. Ularni tahrirlash yoki o‘chirish mumkin emas. Yuklash tanlangan kunning barcha yozuvlarini beradi.</Alert>
    <Card className="p-4 space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <Input type="date" label="Log kuni" value={filters.day} max={today()}
          onChange={(e) => changeFilter("day", e.target.value)} />
        <Select label="Xodim" value={filters.actor_id} onChange={(e) => changeFilter("actor_id", e.target.value)}
          options={[{ value: "", label: "Barcha xodimlar" }, ...(data?.actors || []).map((a) => ({ value: a.id, label: a.name }))]} />
        <Select label="Amal" value={filters.action} onChange={(e) => changeFilter("action", e.target.value)}
          options={[{ value: "", label: "Barcha amallar" }, ...(data?.actions || []).map((a) => ({ value: a, label: logActionLabel(a) }))]} />
        <Select label="Obyekt turi" value={filters.entity} onChange={(e) => changeFilter("entity", e.target.value)}
          options={[{ value: "", label: "Barcha turlar" }, ...["staff", "subject", "group", "student", "parent", "attendance", "message", "bot"].map((e) => ({ value: e, label: logEntityLabel(e) }))]} />
        <Select label="Natija" value={filters.outcome} onChange={(e) => changeFilter("outcome", e.target.value)}
          options={[{ value: "", label: "Barcha natijalar" }, { value: "success", label: "Bajarilgan" }, { value: "rejected", label: "Rad etilgan" }]} />
      </div>
      {days.length > 0 && <div className="flex flex-wrap gap-2" aria-label="Oxirgi log kunlari">
        {days.slice(0, 7).map((d) => <Button key={d.day} size="sm" variant="ghost"
          onClick={() => { setFilters({ day: d.day, actor_id: "", action: "", outcome: "", entity: "" }); setCursors([""]); setSelected(null); }}>
          {logDate(d.day)} · {d.count}</Button>)}
      </div>}
    </Card>
    {downloadError && <Alert variant="danger">{downloadError}</Alert>}
    {error ? <ErrorState message={error} onRetry={() => setRevision((n) => n + 1)} /> : loading ? <LoadingState /> :
      data?.items.length ? <Card className="overflow-hidden">
        <Table><TableHeader><TableRow>{["Vaqt (Toshkent)", "Xodim", "Amal / obyekt", "Natija", "Tafsilot"].map((label) => <TableHead key={label}>{label}</TableHead>)}</TableRow></TableHeader>
          <TableBody>{data.items.map((entry) => <TableRow key={entry.id}>
            <TableCell className="whitespace-nowrap text-xs"><time dateTime={entry.at}>{logTime(entry.at)}</time></TableCell>
            <TableCell><p className="font-medium">{entry.actor?.name || "Tizim xizmati"}</p><p className="text-xs text-slate-500">{entry.actor?.username || entry.source}</p></TableCell>
            <TableCell><p className="font-medium">{logEventLabel(entry)}</p><p className="text-xs text-slate-500 break-words">{entry.entity.name || (entry.action === "http.request" ? `${logValue(entry.details.method)} ${logValue(entry.details.route)}` : logValue(entry.details.group) || logEntityLabel(entry.entity.type))}</p></TableCell>
            <TableCell><Badge variant={logRejected(entry) ? "danger" : "success"}>{logRejected(entry) ? "Rad etilgan" : "Bajarilgan"}</Badge></TableCell>
            <TableCell><Button size="sm" variant="outline" aria-label={`${logEventLabel(entry)} tafsilotlari`}
              onClick={() => setSelected({ owner: currentUser.id, entry })}>Ko‘rish</Button></TableCell>
          </TableRow>)}</TableBody></Table>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 p-4 text-sm">
          <span>{data.total} ta yozuv · {cursors.length}-sahifa</span>
          <div className="flex gap-2"><Button size="sm" variant="outline" disabled={cursors.length < 2}
            onClick={() => setCursors((history) => history.slice(0, -1))}>Oldingi</Button>
            <Button size="sm" variant="outline" disabled={!data.next_cursor}
              onClick={() => setCursors((history) => [...history, data.next_cursor || ""])}>Keyingi</Button></div>
        </div>
      </Card> : <EmptyState icon={<ScrollText className="h-6 w-6" />} title="Log yozuvi topilmadi" description="Boshqa kun yoki filtrni tanlang." />}
    <LogDetails entry={selected?.owner === currentUser.id ? selected.entry : null} onClose={() => setSelected(null)} />
  </div>;
}
