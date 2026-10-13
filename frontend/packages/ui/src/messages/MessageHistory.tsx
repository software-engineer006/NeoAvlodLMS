import React, { useCallback, useEffect, useState } from "react";
import { Clock, RefreshCw, RotateCcw, Ban, Search } from "lucide-react";
import { apiClient } from "../api/client";
import { Alert } from "../components/Alert";
import { Badge, type BadgeProps } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, CardContent } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { Input } from "../components/Input";
import { LoadingState } from "../components/LoadingState";
import { Modal } from "../components/Modal";
import { Select } from "../components/Select";
import {
  MESSAGE_API,
  deliveryLabels,
  formatMessage,
  kindLabels,
  scopeLabels,
  messageError,
  messageTime,
  type DeliveryCounts,
  type DeliveryStatus,
  type MessageDetail,
  type MessageHistoryPage,
} from "./types";

const campaignLabels = {
  queued: "Navbatda",
  completed: "Yakunlangan",
  partial: "Xatolar bor",
  cancelled: "To‘xtatilgan",
};
const variants: Record<string, BadgeProps["variant"]> = {
  pending: "info",
  queued: "info",
  delivered: "success",
  completed: "success",
  failed: "danger",
  partial: "danger",
  skipped: "warning",
  cancelled: "neutral",
};

export const DeliveryBadges: React.FC<{ counts: DeliveryCounts }> = ({
  counts,
}) => (
  <div className="flex flex-wrap gap-2">
    {(Object.keys(deliveryLabels) as DeliveryStatus[])
      .filter((key) => counts[key] > 0)
      .map((key) => (
        <Badge key={key} variant={variants[key]}>
          {deliveryLabels[key]}: {counts[key]}
        </Badge>
      ))}
  </div>
);

interface Props {
  focus: MessageDetail | null;
  onSummary: (counts: DeliveryCounts) => void;
}

export const MessageHistory: React.FC<Props> = ({ focus, onSummary }) => {
  const [data, setData] = useState<MessageHistoryPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<string | null>(
    focus?.campaign.id ?? null,
  );
  const [detail, setDetail] = useState<MessageDetail | null>(focus);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [recipientPage, setRecipientPage] = useState(1);
  const [status, setStatus] = useState("");
  const [action, setAction] = useState<"cancel" | "retry" | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    const load = async () => {
      try {
        const result = await apiClient.get<MessageHistoryPage>(MESSAGE_API, {
          params: { page, page_size: 10, q: debounced },
        });
        if (active) {
          setData(result);
          onSummary(result.summary);
        }
      } catch (err) {
        if (active) setError(messageError(err));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    const timer = setInterval(() => {
      void load();
    }, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [page, debounced, revision, onSummary]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setDetailLoading(true);
    setDetailError(null);
    const load = async () => {
      try {
        const params: Record<string, string | number> = {
          page: recipientPage,
          page_size: 25,
        };
        if (status) params.status = status;
        const result = await apiClient.get<MessageDetail>(
          `${MESSAGE_API}/${selected}`,
          { params },
        );
        if (active) setDetail(result);
      } catch (err) {
        if (active) setDetailError(messageError(err));
      } finally {
        if (active) setDetailLoading(false);
      }
    };
    void load();
    const timer = setInterval(() => {
      void load();
    }, 3000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [selected, recipientPage, status, revision]);
  const openDetail = (id: string) => {
    setDetail(null);
    setSelected(id);
    setRecipientPage(1);
    setStatus("");
    setDetailError(null);
  };
  const closeDetail = useCallback(() => {
    if (!busy) {
      setSelected(null);
      setDetail(null);
      setAction(null);
    }
  }, [busy]);
  const execute = async () => {
    if (!selected || !action || busy) return;
    setBusy(true);
    setDetailError(null);
    try {
      const res = await apiClient.post<MessageDetail>(
        `${MESSAGE_API}/${selected}/${action}`,
        {},
      );
      setDetail(res);
      setAction(null);
      setRecipientPage(1);
      setStatus("");
      setRevision((n) => n + 1);
    } catch (err) {
      setDetailError(messageError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="pt-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-end gap-3 justify-between">
            <div className="w-full sm:max-w-md">
              <Input
                label="Yuborishlar tarixini qidirish"
                placeholder="Sarlavha yoki yuboruvchi"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                leftAddon={<Search className="h-4 w-4" />}
              />
            </div>
            <Button
              variant="outline"
              onClick={() => setRevision((n) => n + 1)}
              leftIcon={<RefreshCw className="h-4 w-4" />}
            >
              Tarixni yangilash
            </Button>
          </div>
          <p className="text-xs text-slate-500">
            Natijalar: {data?.total ?? 0} ta yuborish · Vaqt: Toshkent
          </p>
          {error && <Alert variant="danger">{error}</Alert>}
          {loading && !data ? (
            <LoadingState />
          ) : !data?.items.length ? (
            <EmptyState
              title="Yuborishlar hali yo‘q"
              description="Yangi xabar yuborilgach matni, qabul qiluvchilari va yetkazish holati shu yerda saqlanadi."
            />
          ) : (
            <div className="divide-y divide-slate-100">
              {data.items.map((item) => (
                <div key={item.id} className="py-4 space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <button
                        className="text-sm sm:text-base text-blue-700 font-semibold hover:underline text-left break-words focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
                        onClick={() => openDetail(item.id)}
                      >
                        {item.title}
                      </button>
                      <p className="text-xs text-slate-500 mt-1 flex flex-wrap gap-2">
                        <span>{messageTime(item.created_at)}</span>
                        <span>· {item.author_name}</span>
                        <span>
                          · {scopeLabels[item.audience.scope]} /{" "}
                          {kindLabels[item.audience.kind]}
                        </span>
                      </p>
                    </div>
                    <Badge variant={variants[item.status]}>
                      {campaignLabels[item.status]}
                    </Badge>
                  </div>
                  <DeliveryBadges counts={item.counts} />
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-500">
                      {item.total} ta qabul qiluvchi
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => openDetail(item.id)}
                    >
                      Batafsil ko‘rish
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {data && data.total > 10 && (
            <div className="flex items-center justify-between border-t border-slate-100 pt-4">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 1 || loading}
                onClick={() => setPage((n) => n - 1)}
              >
                Oldingi yuborishlar
              </Button>
              <span className="text-xs text-slate-500">
                {page} / {Math.ceil(data.total / 10)}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page * 10 >= data.total || loading}
                onClick={() => setPage((n) => n + 1)}
              >
                Keyingi yuborishlar
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
      <Modal
        isOpen={Boolean(selected)}
        onClose={closeDetail}
        size="2xl"
        title={
          detail ? `Xabar: ${detail.campaign.title}` : "Yuborish tafsilotlari"
        }
        description="Har bir qabul qiluvchi bo‘yicha Telegram yetkazish holati"
      >
        {detailError && (
          <Alert variant="danger" className="mb-4">
            {detailError}
          </Alert>
        )}
        {detailLoading && !detail ? (
          <LoadingState />
        ) : (
          detail && (
            <div className="space-y-5">
              <div className="flex flex-wrap justify-between gap-3">
                <div className="text-xs text-slate-500">
                  <p>
                    Yuboruvchi:{" "}
                    <span className="font-medium text-slate-700">
                      {detail.campaign.author_name}
                    </span>
                  </p>
                  <p className="mt-1">
                    {messageTime(detail.campaign.created_at)} ·{" "}
                    {kindLabels[detail.campaign.audience.kind]}
                  </p>
                </div>
                <Badge variant={variants[detail.campaign.status]}>
                  {campaignLabels[detail.campaign.status]}
                </Badge>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 whitespace-pre-wrap break-words text-sm leading-6 text-slate-800">
                {formatMessage(detail.campaign.title, detail.campaign.body)}
              </div>
              <DeliveryBadges counts={detail.campaign.counts} />
              {detail.campaign.cancelled_at && (
                <p className="text-xs text-slate-500">
                  To‘xtatilgan: {messageTime(detail.campaign.cancelled_at)}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {detail.campaign.counts.failed > 0 &&
                  !detail.campaign.cancelled_at && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() => setAction("retry")}
                      leftIcon={<RotateCcw className="h-4 w-4" />}
                    >
                      Xatoli yuborishlarni qayta urinish
                    </Button>
                  )}
                {detail.campaign.counts.pending > 0 &&
                  !detail.campaign.cancelled_at && (
                    <Button
                      variant="danger"
                      size="sm"
                      disabled={busy}
                      onClick={() => setAction("cancel")}
                      leftIcon={<Ban className="h-4 w-4" />}
                    >
                      Navbatni to‘xtatish
                    </Button>
                  )}
              </div>
              {action && (
                <div
                  className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-3"
                  role="region"
                  aria-label="Navbat amalini tasdiqlash"
                >
                  <p className="text-sm text-amber-900">
                    {action === "cancel"
                      ? "Faqat navbatdagi xabarlar to‘xtatiladi. Yetkazilgan xabarlar Telegramdan o‘chirilmaydi."
                      : "Faqat xatoli yuborishlar qayta navbatga tushadi. Yetkazilgan xabarlar qayta yuborilmaydi."}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant={action === "cancel" ? "danger" : "primary"}
                      isLoading={busy}
                      onClick={execute}
                    >
                      Amalni tasdiqlash
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      onClick={() => setAction(null)}
                    >
                      Bekor qilish
                    </Button>
                  </div>
                </div>
              )}
              <Select
                label="Yetkazish holati bo‘yicha saralash"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setRecipientPage(1);
                }}
                options={[
                  { value: "", label: "Barcha qabul qiluvchilar" },
                  ...Object.entries(deliveryLabels).map(([value, label]) => ({
                    value,
                    label,
                  })),
                ]}
              />
              <div className="rounded-xl border border-slate-200 divide-y divide-slate-100 max-h-80 overflow-y-auto">
                {detail.recipients.length === 0 ? (
                  <p className="p-4 text-sm text-slate-500">
                    Bu holatda qabul qiluvchi yo‘q.
                  </p>
                ) : (
                  detail.recipients.map((row) => (
                    <div key={row.id} className="p-3 space-y-1">
                      <div className="flex flex-wrap justify-between gap-2">
                        <span className="text-sm font-medium text-slate-800">
                          {row.name}{" "}
                          <span className="text-xs text-slate-400">
                            · {row.kind === "parent" ? "Ota-ona" : "O‘quvchi"}
                          </span>
                        </span>
                        <Badge size="sm" variant={variants[row.status]}>
                          {deliveryLabels[row.status]}
                        </Badge>
                      </div>
                      <p className="text-xs text-slate-500 break-words">
                        {row.group_names.join(" · ")}
                      </p>
                      {row.last_error && (
                        <p
                          className={`text-xs ${row.status === "failed" ? "text-rose-700" : "text-amber-700"}`}
                        >
                          {row.last_error}
                        </p>
                      )}
                      <p className="text-xs text-slate-400">
                        Urinishlar: {row.attempts}
                        {row.delivered_at
                          ? ` · Yetkazilgan: ${messageTime(row.delivered_at)}`
                          : row.status === "pending"
                            ? ` · Keyingi urinish: ${messageTime(row.available_at)}`
                            : ""}
                      </p>
                      {row.retried_at && (
                        <p className="text-xs text-slate-500">
                          Qayta urinish so‘ralgan: {messageTime(row.retried_at)}
                        </p>
                      )}
                    </div>
                  ))
                )}
              </div>
              {detail.total > 25 && (
                <div className="flex justify-between items-center">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={recipientPage <= 1 || busy}
                    onClick={() => setRecipientPage((n) => n - 1)}
                  >
                    Oldingi qabul qiluvchilar
                  </Button>
                  <span className="text-xs text-slate-500">
                    {recipientPage} / {Math.ceil(detail.total / 25)}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={recipientPage * 25 >= detail.total || busy}
                    onClick={() => setRecipientPage((n) => n + 1)}
                  >
                    Keyingi qabul qiluvchilar
                  </Button>
                </div>
              )}
              <p className="text-xs text-slate-400 flex gap-1.5 items-center">
                <Clock className="h-3.5 w-3.5" />
                Yetkazildi — Telegram xabarni qabul qilgan. O‘qilganlik holati
                hisoblanmaydi.
              </p>
            </div>
          )
        )}
      </Modal>
    </div>
  );
};
