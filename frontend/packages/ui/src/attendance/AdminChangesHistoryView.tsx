import { tashkentToday } from "../lib/dates";
import { useState } from "react";
import { Card } from "../components/Card";
import { CalendarInput } from "../components/CalendarInput";
import { Select } from "../components/Select";
import { AttendanceChangesView } from "./AttendanceChangesView";

export function AdminChangesHistoryView({
  groups,
}: {
  groups: Array<{ id: string; name: string }>;
}) {
  const [selection, setSelection] = useState("");
  const [date, setDate] = useState(() =>
    tashkentToday(),
  );
  const group = groups.some((item) => item.id === selection)
    ? selection
    : (groups[0]?.id ?? "");
  const endpoint = `/api/v1/admin/attendance/groups/${group}/attendance/changes?date=${date}`;
  return (
    <Card className="p-5 space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          Davomat o‘zgarishlari
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Kim, qachon va qanday sabab bilan belgilaganini yoki tuzatganini
          ko‘ring.
        </p>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <Select
          label="Audit guruhi"
          value={group}
          onChange={(event) => setSelection(event.target.value)}
          options={groups.map((item) => ({ value: item.id, label: item.name }))}
        />
        <CalendarInput
          label="Audit dars sanasi"
          type="date"
          value={date}
          onValueChange={setDate}
        />
      </div>
      {group && date ? (
        <AttendanceChangesView
          key={endpoint}
          endpoint={endpoint}
          revision={0}
        />
      ) : (
        <p className="text-sm text-slate-500">Guruh va sanani tanlang.</p>
      )}
      <p className="text-xs text-slate-400">
        Tarix o‘zgartirilmaydi. Eski importlar uchun taxminiy audit
        yaratilmagan.
      </p>
    </Card>
  );
}
