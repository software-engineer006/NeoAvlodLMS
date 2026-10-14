import { Modal } from "../components/Modal";
import { Badge } from "../components/Badge";
import { logDate, logEventLabel, logExactUTC, logFieldValue, logRejected, logTime, logValue } from "./format";
import { logPortalLabel } from "./requestLabels";
import type { LogEvent } from "./types";

const fields: Record<string, string> = {
  first_name: "Ism", last_name: "Familiya", username: "Login", role: "Rol",
  status: "Holat", permissions: "Ruxsatlar", name: "Nomi", description: "Tavsif",
  is_active: "Faollik", teacher_id: "O‘qituvchi", subject_id: "Fan", group_id: "Guruh",
  parent_id: "Ota-ona", monthly_price: "Oylik narx", max_students: "Sig‘im",
  days_of_week: "Dars kunlari", start_time: "Boshlanish vaqti", end_time: "Tugash vaqti",
  room_number: "Xona", note: "Izoh", lesson_date: "Dars sanasi", group: "Guruh",
  student: "O‘quvchi", reason: "Sabab", title: "Sarlavha", body: "Xabar matni",
  audience: "Auditoriya", bot_username: "Bot nomi", version: "Versiya",
  finalized_by: "Yakunlagan xodim", finalized_at: "Yakunlash vaqti",
  must_change_password: "Parol yangilash talabi", avatar_url: "Profil rasmi",
};
export function LogDetails({ entry, onClose }: { entry: LogEvent | null; onClose: () => void }) {
  return <Modal isOpen={Boolean(entry)} onClose={onClose} title="Log tafsilotlari" size="2xl"
    description="Saqlangan yozuv faqat o‘qish uchun ochiladi.">
    {entry && <div className="space-y-5 min-w-0 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold">{logEventLabel(entry)}</h3>
        <Badge variant={logRejected(entry) ? "danger" : "success"}>
          {logRejected(entry) ? "Rad etilgan" : "Bajarilgan"}
        </Badge>
      </div>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 rounded-xl bg-slate-50 p-4">
        {[["Xodim", entry.actor ? `${entry.actor.name} (${entry.actor.username || entry.actor.role})` : "Tizim xizmati"],
          ["Vaqt (Toshkent)", logTime(entry.at)], ["Obyekt", entry.entity.name || logValue(entry.details.group)],
          ["Guruh", logValue(entry.details.group)], ["Sabab", logValue(entry.details.reason)], ["Manba", entry.source],
          ["Panel", logPortalLabel(entry) || "—"],
          ["Dars sanasi", logDate(logValue(entry.details.lesson_date))]].map(([label, value]) =>
          <div key={label}><dt className="text-slate-500">{label}</dt>
            <dd className="mt-1 break-words whitespace-pre-wrap font-medium">{value}</dd></div>)}
      </dl>
      {Object.keys(entry.changes).length > 0 && <div className="space-y-3">
        <h4 className="font-semibold">O‘zgarishlar</h4>
        {Object.entries(entry.changes).map(([key, change]) => <div key={key} className="rounded-xl border border-slate-200 p-3">
          <p className="font-medium mb-2">{fields[key] || key}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[["Oldingi qiymat", change.before], ["Yangi qiymat", change.after]].map(([label, value]) =>
              <div key={String(label)} className="rounded-lg bg-slate-50 p-3 min-w-0">
                <p className="text-xs text-slate-500 mb-1">{String(label)}</p>
                <p className="break-words whitespace-pre-wrap">{logFieldValue(key, value)}</p>
              </div>)}
          </div>
        </div>)}
      </div>}
      {entry.private_changed.length > 0 && <p className="rounded-xl bg-amber-50 p-3 text-amber-900">
        Maxfiy maydonlar yangilangan. Ularning qiymatlari xavfsizlik uchun logda saqlanmaydi.
      </p>}
      <details className="rounded-xl border border-slate-200 p-3">
        <summary className="cursor-pointer font-medium">Aniq vaqt va yozuv identifikatori</summary>
        <p className="mt-2 break-all">UTC: {logExactUTC(entry.at)}</p>
        <p className="mt-1 break-all">Log ID: {entry.id}</p>
        {entry.request_id && <p className="mt-1 break-all">So‘rov ID: {entry.request_id}</p>}
        {typeof entry.details.method === "string" && <p className="mt-2 break-all">So‘rov: {logValue(entry.details.method)} {logValue(entry.details.route)}</p>}
        {typeof entry.details.status === "number" && <p className="mt-1">Javob holati: {logValue(entry.details.status)}</p>}
      </details>
    </div>}
  </Modal>;
}
