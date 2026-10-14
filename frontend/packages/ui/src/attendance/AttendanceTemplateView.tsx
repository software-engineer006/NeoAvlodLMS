import { useEffect, useState } from "react";
import type { CurrentUser } from "../api/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { hasPermission, PERMISSIONS } from "../navigation/permissions";
import { formatDateTime } from "../lib/dates";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { LoadingState } from "../components/LoadingState";

interface TemplateData {
  body: string; version: number; preview: string; placeholders: string[];
  updated_at: string | null; changed_by: string | null; editor_name: string | null;
}
const endpoint = "/api/v1/admin/attendance/message-template";
export function AttendanceTemplateView({ currentUser }: { currentUser: CurrentUser }) {
  const allowed = hasPermission(currentUser, PERMISSIONS.ATTENDANCE_WRITE);
  const [data, setData] = useState<TemplateData | null>(null), [body, setBody] = useState("");
  const [preview, setPreview] = useState(""), [previewBody, setPreviewBody] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (!allowed) return;
    let current = true;
    apiClient.get<TemplateData>(endpoint).then(value => {
      if (current) { setData(value); setBody(value.body); setPreview(value.preview); setPreviewBody(value.body); }
    }).catch(failure => { if (current) setError(failure instanceof ApiError ? failure.detail : "Shablon yuklanmadi"); });
    return () => { current = false; };
  }, [allowed]);
  async function act(save: boolean) {
    if (!allowed || busy || !data) return;
    setBusy(true); setError(null); setSaved(false);
    try {
      if (save) {
        const value = await apiClient.put<TemplateData>(endpoint, { body, expected_version: data.version });
        setData(value); setBody(value.body); setPreview(value.preview); setPreviewBody(value.body); setSaved(true);
      } else {
        const value = await apiClient.post<{ message: string }>(`${endpoint}/preview`, { body });
        setPreview(value.message); setPreviewBody(body);
      }
    } catch (failure) { setError(failure instanceof ApiError ? failure.detail : "Shablon saqlanmadi"); }
    finally { setBusy(false); }
  }
  async function checkVersion() {
    if (!allowed || busy) return;
    setBusy(true); setError(null);
    try {
      setData(await apiClient.get<TemplateData>(endpoint));
      setPreview(""); setPreviewBody(""); setSaved(false);
    } catch (failure) { setError(failure instanceof ApiError ? failure.detail : "Versiya yuklanmadi"); }
    finally { setBusy(false); }
  }
  if (!allowed) return <Alert variant="danger">Davomat xabari shablonini tahrirlash uchun ruxsat yo‘q.</Alert>;
  if (!data && !error) return <LoadingState message="Xabar shabloni yuklanmoqda..." />;
  return <div className="space-y-4">
    {error && <Alert variant="danger">{error}</Alert>}{saved && <Alert variant="success">Shablon saqlandi. Keyingi davomat xabarlari shu versiyadan foydalanadi.</Alert>}
    {data && <>
      <p className="text-sm text-slate-500">Versiya: {data.version}. {data.editor_name ? `${data.editor_name} · ${data.updated_at ? formatDateTime(data.updated_at) : "—"}` : "Boshlang‘ich shablon"}</p>
      <Button size="sm" variant="outline" disabled={busy} onClick={checkVersion}>Saqlangan versiyani tekshirish</Button>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4 space-y-3"><label htmlFor="attendance-template-body" className="block font-semibold">Davomat xabari matni</label>
          <textarea id="attendance-template-body" rows={12} maxLength={3000} value={body} disabled={busy}
            onChange={event => { setBody(event.target.value); setPreview(""); setSaved(false); }} className="w-full rounded-lg border border-slate-300 p-3 text-sm font-mono" />
          <p className="text-xs text-slate-500">Belgilarning nomini o‘zgartirmang: {data.placeholders.map(name => `{${name}}`).join(", ")}. Bola, guruh, sana, dars vaqti, holat va feedback saqlanishi shart.</p>
          <details className="text-xs text-slate-500"><summary>Saqlangan versiya matni</summary><pre className="whitespace-pre-wrap break-words font-sans p-2">{data.body}</pre></details>
          <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy || !body.trim()} onClick={() => act(false)}>Matnni ko‘rib chiqish</Button>
            <Button disabled={busy || !preview || previewBody !== body || body === data.body} isLoading={busy} onClick={() => act(true)}>Shablonni saqlash</Button></div>
        </Card>
        <Card className="p-4 space-y-3"><h2 className="font-semibold">Ota-onaga boradigan xabar namunasi</h2>
          <p className="text-xs text-slate-500">Sun’iy ma’lumotli namuna. Ko‘rib chiqish xabar yubormaydi.</p>
          <pre className="whitespace-pre-wrap break-words font-sans text-sm rounded-xl bg-slate-50 p-4">{preview || "Matnni ko‘rib chiqish tugmasini bosing."}</pre>
        </Card>
      </div>
    </>}
  </div>;
}
