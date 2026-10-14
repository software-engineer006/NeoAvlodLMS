import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCheck,
  Clock,
  History,
  Layers,
  MessageSquare,
  Send,
  Users,
} from "lucide-react";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import type { CurrentUser } from "../api/types";
import { Alert } from "../components/Alert";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/Card";
import { Input } from "../components/Input";
import { Modal } from "../components/Modal";
import { Select } from "../components/Select";
import { hasPermission, PERMISSIONS } from "../navigation/permissions";
import { MessageHistory } from "./MessageHistory";
import { RecipientPicker } from "./RecipientPicker";
import {
  MESSAGE_API,
  emptyCounts,
  createRequestId,
  formatMessage,
  kindLabels,
  messageError,
  scopeLabels,
  type AudienceKind,
  type AudienceScope,
  type DeliveryCounts,
  type MessageAudience,
  type MessageDetail,
  type MessageDraft,
  type MessageGroup,
  type MessageHistoryPage,
  type MessagePreview,
  type RecipientKind,
  type RecipientOption,
} from "./types";

const templates = {
  lesson: {
    title: "Dars haqida eslatma",
    body: "Hurmatli ota-onalar va o‘quvchilar, navbatdagi dars bo‘yicha ma’lumot:\n\nSana va vaqtni shu yerga yozing.",
  },
  payment: {
    title: "To‘lov haqida eslatma",
    body: "Hurmatli ota-onalar, oylik to‘lov bo‘yicha markaz administratoriga murojaat qilishingizni so‘raymiz. Rahmat.",
  },
  announcement: {
    title: "Markaz e’loni",
    body: "Hurmatli ota-onalar va o‘quvchilar, sizga quyidagi yangilikni ma’lum qilamiz:\n\nE’lon matnini shu yerga yozing.",
  },
};

export const MessagesManagementView: React.FC<{ currentUser: CurrentUser }> = ({
  currentUser,
}) => {
  const allowed = hasPermission(currentUser, PERMISSIONS.MESSAGES_SEND);
  const [mode, setMode] = useState<"compose" | "history">("compose");
  const [groups, setGroups] = useState<MessageGroup[]>([]);
  const [summary, setSummary] = useState<DeliveryCounts>(emptyCounts);
  const [scope, setScope] = useState<AudienceScope>("selected");
  const [kind, setKind] = useState<AudienceKind>("parents");
  const [pane, setPane] = useState<RecipientKind>("parent");
  const [parentIds, setParentIds] = useState<string[]>([]);
  const [studentIds, setStudentIds] = useState<string[]>([]);
  const [groupIds, setGroupIds] = useState<string[]>([]);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [previewState, setPreviewState] = useState<{
    key: string;
    value: MessagePreview;
  } | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [sending, setSending] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [focus, setFocus] = useState<MessageDetail | null>(null);
  const requestId = useRef<string | null>(null);
  const sendingRef = useRef(false);
  const audience: MessageAudience = {
    scope,
    kind,
    group_ids: scope === "groups" ? groupIds : [],
    parent_ids: scope === "selected" && kind !== "students" ? parentIds : [],
    student_ids: scope === "selected" && kind !== "parents" ? studentIds : [],
  };
  const draft: MessageDraft = {
    title: title.trim(),
    body: body.trim(),
    audience,
  };
  const key = JSON.stringify(draft);
  const latestKey = useRef(key);
  latestKey.current = key;
  const preview = previewState?.key === key ? previewState.value : null;
  const text = formatMessage(title, body);
  const selectionValid =
    scope === "all" ||
    (scope === "groups"
      ? groupIds.length > 0
      : audience.parent_ids.length + audience.student_ids.length > 0);
  const valid =
    selectionValid &&
    Boolean(title.trim()) &&
    Boolean(body.trim()) &&
    text.length <= 4096;
  const selectedCount = parentIds.length + studentIds.length;
  const onSummary = useCallback(
    (counts: DeliveryCounts) => setSummary(counts),
    [],
  );
  useEffect(() => {
    setPreviewState(null);
    setConfirm(false);
    requestId.current = null;
  }, [key]);
  useEffect(() => {
    if (!allowed) return;
    let active = true;
    Promise.all([
      apiClient.get<MessageGroup[]>(`${MESSAGE_API}/groups`),
      apiClient.get<MessageHistoryPage>(MESSAGE_API),
    ])
      .then(([groupRows, history]) => {
        if (active) {
          setGroups(groupRows);
          setSummary(history.summary);
        }
      })
      .catch((err) => {
        if (active) setError(messageError(err));
      });
    return () => {
      active = false;
    };
  }, [allowed]);
  useEffect(() => {
    if (!title && !body && !selectedCount && !groupIds.length) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [title, body, selectedCount, groupIds.length]);
  const chooseKind = (value: AudienceKind) => {
    setKind(value);
    if (value === "parents") {
      setStudentIds([]);
      setPane("parent");
    }
    if (value === "students") {
      setParentIds([]);
      setPane("student");
    }
  };
  const toggle = (row: RecipientOption) => {
    const setter = row.kind === "parent" ? setParentIds : setStudentIds;
    setter((ids) =>
      ids.includes(row.id)
        ? ids.filter((id) => id !== row.id)
        : [...ids, row.id],
    );
    setLabels((prev) => ({ ...prev, [`${row.kind}:${row.id}`]: row.name }));
  };
  const selectPage = (rows: RecipientOption[]) => {
    const parents = rows
      .filter((row) => row.kind === "parent")
      .map((row) => row.id);
    const students = rows
      .filter((row) => row.kind === "student")
      .map((row) => row.id);
    setParentIds((ids) => [...new Set([...ids, ...parents])]);
    setStudentIds((ids) => [...new Set([...ids, ...students])]);
    setLabels((prev) => ({
      ...prev,
      ...Object.fromEntries(
        rows.map((row) => [`${row.kind}:${row.id}`, row.name]),
      ),
    }));
  };
  const clear = () => {
    setTitle("");
    setBody("");
    setParentIds([]);
    setStudentIds([]);
    setGroupIds([]);
    setScope("selected");
    setLabels({});
    setError(null);
  };
  const review = async () => {
    if (!valid || reviewing || sending) return;
    const capturedKey = key;
    setReviewing(true);
    setError(null);
    setPreviewState(null);
    try {
      const result = await apiClient.post<MessagePreview>(
        `${MESSAGE_API}/preview`,
        draft,
      );
      if (latestKey.current === capturedKey) {
        setPreviewState({ key: capturedKey, value: result });
        if (!requestId.current) requestId.current = createRequestId();
      }
    } catch (err) {
      if (latestKey.current === capturedKey) setError(messageError(err));
    } finally {
      setReviewing(false);
    }
  };
  const submit = async () => {
    if (
      !preview ||
      !preview.bot_configured ||
      !preview.eligible ||
      sendingRef.current
    )
      return;
    sendingRef.current = true;
    setSending(true);
    setError(null);
    if (!requestId.current) requestId.current = createRequestId();
    try {
      const result = await apiClient.post<MessageDetail>(MESSAGE_API, {
        ...draft,
        request_id: requestId.current,
        preview_digest: preview.digest,
      });
      setConfirm(false);
      setFocus(result);
      setSuccess(
        `“${result.campaign.title}” xabari navbatga qo‘shildi. Yetkazish holatini tarixdan kuzating.`,
      );
      clear();
      setMode("history");
    } catch (err) {
      setError(messageError(err));
      if (err instanceof ApiError && err.status === 409) {
        setConfirm(false);
        setPreviewState(null);
      }
    } finally {
      setSending(false);
      sendingRef.current = false;
    }
  };
  if (!allowed)
    return (
      <Alert variant="danger" title="Bo‘limga kirish uchun ruxsat yo‘q">
        Xabarlar bo‘limini administratorga superadmin ruxsat orqali ochib
        beradi.
      </Alert>
    );
  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div className="flex flex-col sm:flex-row gap-4 justify-between sm:items-center">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-blue-600 p-3 text-white shadow-xs">
            <MessageSquare className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Xabarlar</h1>
            <p className="text-sm text-slate-500 mt-0.5">
              Ota-onalar va o‘quvchilar bilan Telegram orqali bog‘laning
            </p>
          </div>
        </div>
        <Badge variant="info">Telegram bot orqali</Badge>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          {
            label: "Yetkazilgan",
            value: summary.delivered,
            icon: CheckCheck,
            color: "text-emerald-600 bg-emerald-50",
          },
          {
            label: "Navbatdagi",
            value: summary.pending,
            icon: Clock,
            color: "text-blue-600 bg-blue-50",
          },
          {
            label: "Xatoli",
            value: summary.failed,
            icon: AlertCircle,
            color: "text-rose-600 bg-rose-50",
          },
          {
            label: "Yuborilmagan",
            value: summary.skipped,
            icon: Users,
            color: "text-amber-600 bg-amber-50",
          },
        ].map((item) => (
          <Card key={item.label}>
            <CardContent className="pt-4 pb-4 flex gap-3 items-center">
              <div className={`p-2 rounded-lg ${item.color}`}>
                <item.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs text-slate-500">{item.label}</p>
                <p className="text-xl font-bold text-slate-900">{item.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="text-xs text-slate-400 -mt-2">
        Barcha yuborishlar bo‘yicha yetkazish statistikasi
      </p>
      <div
        className="flex gap-1 p-1 rounded-xl bg-slate-100 w-fit"
        role="tablist"
        aria-label="Xabarlar bo‘limi"
      >
        <button
          role="tab"
          aria-selected={mode === "compose"}
          disabled={sending}
          onClick={() => {
            setMode("compose");
            setFocus(null);
          }}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold ${mode === "compose" ? "bg-white shadow-xs text-blue-700" : "text-slate-500"}`}
        >
          <Send className="h-4 w-4" />
          Yangi xabar
        </button>
        <button
          role="tab"
          aria-selected={mode === "history"}
          disabled={sending}
          onClick={() => {
            setMode("history");
            setFocus(null);
          }}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold ${mode === "history" ? "bg-white shadow-xs text-blue-700" : "text-slate-500"}`}
        >
          <History className="h-4 w-4" />
          Yuborishlar tarixi
        </button>
      </div>
      {success && (
        <Alert variant="success" title="Xabar qabul qilindi">
          {success}
        </Alert>
      )}
      {error && (
        <Alert variant="danger" title="Amal bajarilmadi">
          {error}
        </Alert>
      )}
      {mode === "history" ? (
        <MessageHistory focus={focus} onSummary={onSummary} />
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 items-start">
          <div className="xl:col-span-2 space-y-5">
            <Card>
              <CardHeader>
                <CardTitle>1. Qabul qiluvchilar</CardTitle>
                <CardDescription>
                  Kimga yuborishni va ro‘yxatni tanlang
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {(Object.keys(kindLabels) as AudienceKind[]).map((value) => (
                    <Button
                      key={value}
                      size="sm"
                      variant={kind === value ? "primary" : "outline"}
                      aria-pressed={kind === value}
                      disabled={sending}
                      onClick={() => chooseKind(value)}
                    >
                      {kindLabels[value]}
                    </Button>
                  ))}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {(
                    [
                      {
                        value: "selected",
                        icon: Users,
                        help: "Alohida odamlarni belgilang",
                      },
                      {
                        value: "groups",
                        icon: Layers,
                        help: "Bir yoki bir nechta guruh",
                      },
                      {
                        value: "all",
                        icon: Send,
                        help: "Faol ro‘yxatdagi barchasi",
                      },
                    ] as const
                  ).map((option) => (
                    <button
                      key={option.value}
                      aria-pressed={scope === option.value}
                      disabled={sending}
                      onClick={() => setScope(option.value)}
                      className={`rounded-xl border p-3 text-left transition-colors ${scope === option.value ? "border-blue-500 bg-blue-50 ring-1 ring-blue-500" : "border-slate-200 hover:bg-slate-50"}`}
                    >
                      <option.icon
                        className={`h-4 w-4 mb-2 ${scope === option.value ? "text-blue-600" : "text-slate-400"}`}
                      />
                      <span className="block font-semibold text-sm text-slate-800">
                        {scopeLabels[option.value]}
                      </span>
                      <span className="text-xs text-slate-500">
                        {option.help}
                      </span>
                    </button>
                  ))}
                </div>
                {scope === "selected" && (
                  <>
                    {kind === "both" && (
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant={pane === "parent" ? "secondary" : "ghost"}
                          disabled={sending}
                          onClick={() => setPane("parent")}
                        >
                          Ota-onalarni tanlash ({parentIds.length})
                        </Button>
                        <Button
                          size="sm"
                          variant={pane === "student" ? "secondary" : "ghost"}
                          disabled={sending}
                          onClick={() => setPane("student")}
                        >
                          O‘quvchilarni tanlash ({studentIds.length})
                        </Button>
                      </div>
                    )}
                    <RecipientPicker
                      kind={pane}
                      groups={groups}
                      selected={pane === "parent" ? parentIds : studentIds}
                      disabled={sending}
                      onToggle={toggle}
                      onSelectPage={selectPage}
                    />
                    {selectedCount > 0 && (
                      <div className="rounded-xl bg-blue-50 p-3 text-xs text-blue-800 space-y-2">
                        <div className="flex justify-between items-center gap-3">
                          <strong>
                            Tanlangan: {parentIds.length} ota-ona,{" "}
                            {studentIds.length} o‘quvchi
                          </strong>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={sending}
                            onClick={() => {
                              setParentIds([]);
                              setStudentIds([]);
                            }}
                          >
                            Tanlovni tozalash
                          </Button>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {[
                            ...parentIds.map((id) => `parent:${id}`),
                            ...studentIds.map((id) => `student:${id}`),
                          ]
                            .slice(0, 12)
                            .map((id) => (
                              <span
                                key={id}
                                className="rounded-md border border-blue-200 bg-white px-2 py-1"
                              >
                                {labels[id] || "Tanlangan qabul qiluvchi"}
                              </span>
                            ))}
                          {selectedCount > 12 && (
                            <span className="py-1">
                              va yana {selectedCount - 12} ta
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </>
                )}
                {scope === "groups" && (
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {groups.length ? (
                      groups.map((group) => (
                        <label
                          key={group.id}
                          className={`flex gap-3 items-start p-3 rounded-xl border cursor-pointer ${groupIds.includes(group.id) ? "bg-blue-50 border-blue-300" : "border-slate-200"}`}
                        >
                          <input
                            type="checkbox"
                            className="mt-1 rounded-sm border-slate-300 text-blue-600 focus:ring-blue-500"
                            disabled={sending}
                            checked={groupIds.includes(group.id)}
                            aria-label={`Guruhni tanlash: ${group.name}`}
                            onChange={() =>
                              setGroupIds((ids) =>
                                ids.includes(group.id)
                                  ? ids.filter((id) => id !== group.id)
                                  : [...ids, group.id],
                              )
                            }
                          />
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-slate-700 break-words">
                              {group.name}
                            </p>
                            <p className="text-xs text-slate-500 mt-1">
                              {group.students} ta faol o‘quvchi
                            </p>
                          </div>
                        </label>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">
                        Faol guruh topilmadi.
                      </p>
                    )}
                  </div>
                )}
                {scope === "all" && (
                  <Alert variant="info" title="Faol ro‘yxatdagi barchaga">
                    {kindLabels[kind]} barcha faol guruhlar bo‘yicha tanlanadi.
                    Bir Telegram hisobiga bitta xabar yuboriladi. Yuborishdan
                    oldin jami qabul qiluvchilar sonini ko‘rib tasdiqlaysiz.
                  </Alert>
                )}
                <p className="text-xs text-slate-500">
                  Botga ulanmagan hisoblar alohida ko‘rsatiladi va ularga xabar
                  yuborilmaydi.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>2. Xabar matni</CardTitle>
                <CardDescription>
                  Sarlavha va matn Telegramga ko‘rsatilgan shaklda yuboriladi
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Select
                  label="Tayyor matn namunasi"
                  value=""
                  disabled={sending}
                  onChange={(e) => {
                    const template =
                      templates[e.target.value as keyof typeof templates];
                    if (template) {
                      setTitle(template.title);
                      setBody(template.body);
                    }
                  }}
                  options={[
                    { value: "", label: "Namuna tanlash (ixtiyoriy)" },
                    { value: "lesson", label: "Dars haqida eslatma" },
                    { value: "payment", label: "To‘lov haqida eslatma" },
                    { value: "announcement", label: "Markaz e’loni" },
                  ]}
                />
                <Input
                  label="Xabar sarlavhasi"
                  value={title}
                  maxLength={120}
                  required
                  disabled={sending}
                  placeholder="Masalan: Ertangi dars haqida"
                  onChange={(e) => setTitle(e.target.value)}
                />
                <div>
                  <label
                    htmlFor="message-body"
                    className="block text-sm font-medium text-slate-700 mb-1"
                  >
                    Xabar matni <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    id="message-body"
                    value={body}
                    disabled={sending}
                    maxLength={4096}
                    rows={7}
                    placeholder="Xabaringizni yozing..."
                    onChange={(e) => setBody(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 p-3 text-sm leading-6 text-slate-800 focus:ring-2 focus:ring-blue-500 focus:outline-hidden disabled:bg-slate-50"
                  />
                  <div className="flex justify-between gap-3 mt-1">
                    <p className="text-xs text-slate-500">
                      Sarlavha va markaz nomi umumiy limitga kiradi.
                    </p>
                    <p
                      className={`text-xs font-medium ${text.length > 4096 ? "text-red-600" : "text-slate-400"}`}
                    >
                      {text.length} / 4096
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap justify-between gap-3">
                  <Button variant="ghost" disabled={sending} onClick={clear}>
                    Formani tozalash
                  </Button>
                  <Button
                    onClick={review}
                    isLoading={reviewing}
                    disabled={!valid || sending}
                    leftIcon={<Send className="h-4 w-4" />}
                  >
                    Qabul qiluvchilarni ko‘rib chiqish
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
          <Card className="xl:sticky xl:top-5">
            <CardHeader>
              <CardTitle>3. Ko‘rinishi va tasdiqlash</CardTitle>
              <CardDescription>
                Telegramdagi xabar matni va yuborish ro‘yxati
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl border border-sky-100 bg-sky-50 p-4">
                <div className="rounded-xl bg-white border border-slate-100 p-4 text-sm leading-6 whitespace-pre-wrap break-words shadow-xs min-h-32">
                  {title || body
                    ? text
                    : "Xabar yozilgach ko‘rinishi shu yerda paydo bo‘ladi."}
                </div>
              </div>
              {preview ? (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl bg-blue-50 p-3">
                      <p className="text-xs text-blue-600">Yuboriladigan</p>
                      <p className="text-2xl font-bold text-blue-800">
                        {preview.eligible}
                      </p>
                    </div>
                    <div className="rounded-xl bg-slate-50 p-3">
                      <p className="text-xs text-slate-500">Jami tanlangan</p>
                      <p className="text-2xl font-bold text-slate-800">
                        {preview.total}
                      </p>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500">
                    {preview.parents} ota-ona · {preview.students} o‘quvchi ·
                    Ulanmagan: {preview.unlinked} · Takroriy hisob:{" "}
                    {preview.duplicates}
                  </p>
                  {!preview.bot_configured && (
                    <Alert variant="warning" title="Bot sozlanmagan">
                      Yuborish uchun superadmin Telegram botni sozlashi kerak.
                    </Alert>
                  )}
                  {preview.eligible === 0 && (
                    <Alert
                      variant="warning"
                      title="Botga ulangan qabul qiluvchi yo‘q"
                    >
                      O‘quvchi va ota-ona profilidagi bot havolasidan Telegramga
                      ulanish kerak.
                    </Alert>
                  )}
                  {preview.unlinked > 0 && preview.eligible > 0 && (
                    <Alert variant="warning">
                      {preview.unlinked} ta ulanmagan hisobga xabar
                      yuborilmaydi. Qolgan {preview.eligible} ta Telegram
                      hisobiga yuboriladi.
                    </Alert>
                  )}
                  <Button
                    className="w-full"
                    disabled={
                      !preview.bot_configured || !preview.eligible || sending
                    }
                    onClick={() => setConfirm(true)}
                    leftIcon={<Send className="h-4 w-4" />}
                  >
                    Yuborishni tasdiqlash
                  </Button>
                </>
              ) : (
                <p className="text-sm text-slate-500">
                  Qabul qiluvchilar va matnni tayyorlab, “Ko‘rib chiqish”
                  tugmasini bosing. Matn yoki ro‘yxat o‘zgarsa, qayta ko‘rib
                  chiqish kerak.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
      <Modal
        isOpen={confirm}
        onClose={() => {
          if (!sending) setConfirm(false);
        }}
        title="Xabar yuborishni tasdiqlash"
        description="Tasdiqlagach xabar navbatga qo‘shiladi"
        footer={
          <>
            <Button
              variant="outline"
              disabled={sending}
              onClick={() => setConfirm(false)}
            >
              Orqaga
            </Button>
            <Button
              onClick={submit}
              isLoading={sending}
              disabled={!preview?.eligible || !preview.bot_configured}
              leftIcon={<Send className="h-4 w-4" />}
            >
              Navbatga qo‘shish
            </Button>
          </>
        }
      >
        {preview && (
          <div className="space-y-4">
            <Alert
              variant="info"
              title={`${preview.eligible} ta Telegram hisobiga yuboriladi`}
            >
              {scopeLabels[scope]} · {kindLabels[kind]}. Ulanmagan:{" "}
              {preview.unlinked}; takroriy: {preview.duplicates}.
            </Alert>
            <div className="rounded-xl bg-slate-50 p-4 text-sm whitespace-pre-wrap break-words leading-6">
              {preview.message}
            </div>
            <p className="text-xs text-slate-500">
              Ro‘yxat namunasi:{" "}
              {preview.sample
                .slice(0, 8)
                .map((row) => row.name)
                .join(", ")}
              {preview.total > 8 ? ` va yana ${preview.total - 8} ta` : ""}
            </p>
            {error && <Alert variant="danger">{error}</Alert>}
          </div>
        )}
      </Modal>
    </div>
  );
};
