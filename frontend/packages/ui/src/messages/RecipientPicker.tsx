import React, { useEffect, useState } from "react";
import { Search, RefreshCw } from "lucide-react";
import { apiClient } from "../api/client";
import { Alert } from "../components/Alert";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import {
  MESSAGE_API,
  messageError,
  type MessageGroup,
  type RecipientKind,
  type RecipientOption,
  type RecipientPage,
} from "./types";

interface Props {
  kind: RecipientKind;
  groups: MessageGroup[];
  selected: string[];
  disabled: boolean;
  onToggle: (row: RecipientOption) => void;
  onSelectPage: (rows: RecipientOption[]) => void;
}

export const RecipientPicker: React.FC<Props> = ({
  kind,
  groups,
  selected,
  disabled,
  onToggle,
  onSelectPage,
}) => {
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [group, setGroup] = useState("");
  const [connection, setConnection] = useState("");
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<RecipientPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    setPage(1);
  }, [kind]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    const params: Record<string, string | number | boolean> = {
      kind,
      page,
      page_size: 25,
    };
    if (debounced) params.q = debounced;
    if (group) params.group_id = group;
    if (connection) params.connected = connection === "connected";
    apiClient
      .get<RecipientPage>(`${MESSAGE_API}/recipients`, { params })
      .then((res) => {
        if (active) setData(res);
      })
      .catch((err) => {
        if (active) setError(messageError(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [kind, page, debounced, group, connection, revision]);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="sm:col-span-2">
          <Input
            label="Qabul qiluvchini qidirish"
            placeholder="Ism, farzand yoki guruh nomi"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            disabled={disabled}
            leftAddon={<Search className="h-4 w-4" />}
          />
        </div>
        <Select
          label="Guruh bo‘yicha qidirish"
          value={group}
          disabled={disabled}
          onChange={(e) => {
            setGroup(e.target.value);
            setPage(1);
          }}
          options={[
            { value: "", label: "Barcha guruhlar" },
            ...groups.map((g) => ({ value: g.id, label: g.name })),
          ]}
        />
        <Select
          label="Telegram holati"
          value={connection}
          disabled={disabled}
          onChange={(e) => {
            setConnection(e.target.value);
            setPage(1);
          }}
          options={[
            { value: "", label: "Barchasi" },
            { value: "connected", label: "Botga ulangan" },
            { value: "unlinked", label: "Botga ulanmagan" },
          ]}
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>
          {kind === "parent" ? "Ota-onalar" : "O‘quvchilar"}: {data?.total ?? 0}{" "}
          · Tanlangan: {selected.length}
        </span>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="ghost"
            disabled={
              disabled || loading || !data?.items.some((r) => r.connected)
            }
            onClick={() =>
              onSelectPage(data?.items.filter((r) => r.connected) ?? [])
            }
          >
            Sahifadagi ulanganlarni tanlash
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={disabled || loading}
            aria-label="Qabul qiluvchilarni yangilash"
            onClick={() => setRevision((n) => n + 1)}
            leftIcon={<RefreshCw className="h-4 w-4" />}
          />
        </div>
      </div>
      {error ? (
        <Alert variant="danger" title="Ro‘yxat yuklanmadi">
          {error}
        </Alert>
      ) : loading ? (
        <LoadingState />
      ) : !data?.items.length ? (
        <EmptyState
          title="Qabul qiluvchi topilmadi"
          description="Faol guruhdagi o‘quvchilar va ularning ota-onalari ko‘rsatiladi. Qidiruvni o‘zgartiring yoki o‘quvchi profilidagi ota-ona ma’lumotini to‘ldiring."
          className="py-6"
        />
      ) : (
        <div className="max-h-80 overflow-y-auto rounded-xl border border-slate-200 divide-y divide-slate-100">
          {data.items.map((row) => (
            <label
              key={`${row.kind}:${row.id}`}
              className={`flex gap-3 items-start p-3 cursor-pointer transition-colors ${selected.includes(row.id) ? "bg-blue-50" : "bg-white hover:bg-slate-50"}`}
            >
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 shrink-0 rounded-sm border-slate-300 text-blue-600 focus:ring-blue-500"
                disabled={disabled}
                checked={selected.includes(row.id)}
                onChange={() => onToggle(row)}
                aria-label={`Tanlash: ${row.name} (${row.group_names.join(", ")})`}
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap gap-2 items-center">
                  <span className="text-sm font-semibold text-slate-800">
                    {row.name}
                  </span>
                  <Badge
                    size="sm"
                    variant={row.connected ? "success" : "warning"}
                  >
                    {row.connected ? "Ulangan" : "Ulanmagan"}
                  </Badge>
                </div>
                <p className="text-xs text-slate-500 mt-1 break-words">
                  {row.group_names.join(" · ")}
                </p>
                {row.kind === "parent" && (
                  <p className="text-xs text-slate-500 mt-0.5">
                    Farzandlar: {row.student_names.join(", ")}
                  </p>
                )}
                {row.connection_reason && (
                  <p className="text-xs text-amber-700 mt-0.5">
                    {row.connection_reason}
                  </p>
                )}
              </div>
            </label>
          ))}
        </div>
      )}
      {data && data.total > 25 && (
        <div className="flex justify-between items-center pt-2">
          <Button
            variant="outline"
            size="sm"
            disabled={disabled || page <= 1 || loading}
            onClick={() => setPage((n) => n - 1)}
          >
            Oldingi
          </Button>
          <span className="text-xs text-slate-500">
            {page} / {Math.ceil(data.total / 25)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={disabled || page * 25 >= data.total || loading}
            onClick={() => setPage((n) => n + 1)}
          >
            Keyingi
          </Button>
        </div>
      )}
    </div>
  );
};
