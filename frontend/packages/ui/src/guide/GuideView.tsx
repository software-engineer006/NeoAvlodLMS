import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  PanelsTopLeft,
  Search,
  ShieldCheck,
  ZoomIn,
} from "lucide-react";
import type { CurrentUser, PortalType } from "../api/types";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { Modal } from "../components/Modal";
import {
  canReadGuide,
  guideSearch,
  visibleGuideTopics,
  type GuideTopic,
} from "./types";
import { GuidePreview } from "./scenes/GuidePreview";

interface Props {
  currentUser: CurrentUser;
  portal: PortalType;
  topics: GuideTopic[];
  onNavigate?: (tab: string) => void;
}

export function GuideView({ currentUser, portal, topics, onNavigate }: Props) {
  const [search, setSearch] = useState("");
  const [section, setSection] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [zoomId, setZoomId] = useState<string | null>(null);
  const [learned, setLearned] = useState<string[]>([]);
  const allowed = useMemo(
    () => visibleGuideTopics(currentUser, portal, topics),
    [currentUser, portal, topics],
  );
  const query = guideSearch(search);
  const sections = [...new Set(allowed.map((topic) => topic.section))];
  const filtered = allowed.filter(
    (topic) =>
      (!section || topic.section === section) &&
      (!query ||
        guideSearch(
          [
            topic.title,
            topic.summary,
            topic.section,
            ...topic.steps.flatMap((step) => [step.title, step.text]),
            ...topic.tips,
          ].join(" "),
        ).includes(query)),
  );
  const selected =
    filtered.find((topic) => topic.id === selectedId) ?? filtered[0];
  const selectedIndex = selected ? filtered.indexOf(selected) : -1;
  const zoom = allowed.find((topic) => topic.id === zoomId);
  const completed = allowed.filter((topic) =>
    learned.includes(topic.id),
  ).length;
  const select = (id: string) => {
    setSelectedId(id);
    setZoomId(null);
  };
  if (!canReadGuide(currentUser, portal)) {
    return (
      <Alert variant="danger" title="Qo‘llanmaga kirish cheklangan">
        Bu qo‘llanma tegishli portalning faol hisoblari uchun.
      </Alert>
    );
  }
  const roleName =
    portal === "teacher"
      ? "O‘qituvchi"
      : currentUser.role === "superadmin"
        ? "Superadmin"
        : "Administrator";
  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div className="rounded-2xl bg-slate-900 px-5 py-6 sm:p-7 text-white relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-5">
          <div className="flex gap-4 items-start">
            <div className="p-3 rounded-xl bg-blue-500/20 border border-blue-400/20">
              <BookOpen className="w-6 h-6 text-blue-300" />
            </div>
            <div>
              <p className="text-xs font-semibold text-blue-300 uppercase tracking-wider">
                NeoAvlod bilim markazi
              </p>
              <h1 className="text-2xl sm:text-3xl font-bold mt-1">Qo‘llanma</h1>
              <p className="text-sm text-slate-300 mt-2 max-w-xl">
                {roleName} uchun namuna ekranlari va bosqichma-bosqich amaliy
                yo‘riqnomalar.
              </p>
            </div>
          </div>
          <div className="flex gap-5 text-sm border-t sm:border-t-0 border-slate-700 pt-4 sm:pt-0 shrink-0">
            <div>
              <strong className="block text-2xl">{allowed.length}</strong>
              <span className="text-slate-400 text-xs">mavzu</span>
            </div>
            <div>
              <strong className="block text-2xl">
                {allowed.reduce((sum, topic) => sum + topic.steps.length, 0)}
              </strong>
              <span className="text-slate-400 text-xs">amaliy qadam</span>
            </div>
            <div>
              <strong className="block text-2xl">{completed}</strong>
              <span className="text-slate-400 text-xs">o‘rganildi</span>
            </div>
          </div>
        </div>
      </div>
      <div className="flex gap-2 text-xs text-slate-500 items-start">
        <ShieldCheck className="w-4 h-4 shrink-0 text-blue-600" />
        <p>
          {currentUser.role === "superadmin"
            ? "Sizga barcha superadmin va administrator mavzulari ochiq."
            : portal === "teacher"
              ? "Yo‘riqnomalar o‘zingizga biriktirilgan guruhlar bilan ishlash uchun."
              : "Faqat hisobingizga berilgan ruxsatlar bo‘yicha mavzular ko‘rsatiladi."}{" "}
          Namuna ekranlaridagi ism va ma’lumotlar o‘rganish uchun. Namuna ichida hech qanday amal bajarilmaydi.
        </p>
      </div>
      <Card className="p-4 space-y-3">
        <Input
          label="Qo‘llanmadan qidirish"
          placeholder="Masalan: davomat, Telegram, parol yoki guruh"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          leftAddon={<Search className="w-4 h-4" />}
        />
        <div className="flex flex-wrap gap-2" aria-label="Qo‘llanma bo‘limlari">
          {["", ...sections].map((value) => (
            <Button
              key={value}
              variant={section === value ? "primary" : "outline"}
              size="sm"
              aria-pressed={section === value}
              onClick={() => setSection(value)}
            >
              {value || "Barcha mavzular"}
            </Button>
          ))}
        </div>
      </Card>
      {!selected ? (
        <Card className="p-8 text-center space-y-3">
          <Search className="w-8 h-8 text-slate-300 mx-auto" />
          <h2 className="font-semibold text-slate-800">Mavzu topilmadi</h2>
          <p className="text-sm text-slate-500">
            Qidiruv yoki bo‘limni o‘zgartiring. Ruxsat berilmagan mavzu
            qidiruvda ham ochilmaydi.
          </p>
          <Button
            variant="outline"
            onClick={() => {
              setSearch("");
              setSection("");
            }}
          >
            Qidiruvni tozalash
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)] gap-5 items-start">
          <Card className="p-3 lg:sticky lg:top-4">
            <p className="text-xs text-slate-500 px-2 pt-1 pb-3">
              {filtered.length} ta mavzu · mundarija
            </p>
            <nav
              aria-label="Qo‘llanma mavzulari"
              className="max-h-64 lg:max-h-[70vh] overflow-y-auto space-y-1"
            >
              {filtered.map((topic) => (
                <button
                  key={topic.id}
                  onClick={() => select(topic.id)}
                  aria-current={selected.id === topic.id ? "page" : undefined}
                  className={`w-full flex gap-2 items-start rounded-lg p-3 text-left transition-colors ${selected.id === topic.id ? "bg-blue-50 text-blue-800 ring-1 ring-blue-100" : "hover:bg-slate-50 text-slate-700"}`}
                >
                  <span className="min-w-0 flex-1">
                    <span className="text-[10px] uppercase tracking-wider text-slate-400 block mb-1">
                      {topic.section}
                    </span>
                    <span className="text-sm font-medium block">
                      {topic.title}
                    </span>
                  </span>
                  {learned.includes(topic.id) ? (
                    <CheckCircle2
                      className="w-4 h-4 text-emerald-600 shrink-0 mt-1"
                      aria-label="O‘rganilgan"
                    />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-400 shrink-0 mt-1" />
                  )}
                </button>
              ))}
            </nav>
          </Card>
          <article className="min-w-0 space-y-4" aria-label={selected.title}>
            <Card className="p-5 sm:p-6 space-y-5">
              <header>
                <p className="text-xs font-semibold text-blue-600 mb-2">
                  {selected.section} · {selectedIndex + 1} / {filtered.length}
                </p>
                <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                  {selected.title}
                </h2>
                <p className="text-sm text-slate-500 leading-6 mt-2">
                  {selected.summary}
                </p>
              </header>
              <figure className="rounded-xl border border-slate-200 overflow-hidden bg-slate-50">
                <GuidePreview scene={selected.scene} description={selected.previewAlt} />
                <figcaption className="p-3 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
                  <span className="flex gap-2"><PanelsTopLeft className="w-4 h-4 shrink-0" /> Raqamli belgilar quyidagi qadamlarga mos.</span>
                  <Button size="sm" variant="outline" leftIcon={<ZoomIn className="h-4 w-4" />}
                    onClick={() => setZoomId(selected.id)} aria-label={`Namunani kattalashtirish: ${selected.title}`}>
                    Kattalashtirish
                  </Button>
                </figcaption>
              </figure>
              <ol className="space-y-4" aria-label="Amaliy qadamlar">
                {selected.steps.map((step, index) => (
                  <li key={`${selected.id}-${index}`} className="flex gap-3">
                    <span className="w-8 h-8 rounded-full bg-blue-600 text-white font-semibold text-sm grid place-items-center shrink-0">
                      {index + 1}
                    </span>
                    <div className="min-w-0">
                      <h3 className="font-semibold text-sm text-slate-900 pt-1">
                        {step.title}
                      </h3>
                      <p className="mt-1 text-sm text-slate-600 leading-6">
                        {step.text}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
              {selected.tips.length > 0 && (
                <div className="rounded-xl bg-amber-50 border border-amber-100 p-4 space-y-2">
                  <p className="text-xs font-semibold text-amber-900">
                    Eslab qoling
                  </p>
                  {selected.tips.map((tip) => (
                    <p
                      key={tip}
                      className="text-sm text-amber-900/90 leading-6"
                    >
                      {tip}
                    </p>
                  ))}
                </div>
              )}
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
                <Button
                  size="sm"
                  variant={
                    learned.includes(selected.id) ? "secondary" : "outline"
                  }
                  leftIcon={<CheckCircle2 className="w-4 h-4" />}
                  aria-pressed={learned.includes(selected.id)}
                  onClick={() =>
                    setLearned((values) =>
                      values.includes(selected.id)
                        ? values.filter((id) => id !== selected.id)
                        : [...values, selected.id],
                    )
                  }
                >
                  {learned.includes(selected.id) ? "O‘rganildi" : "Tushundim"}
                </Button>
                {selected.destination && onNavigate && (
                  <Button
                    size="sm"
                    onClick={() => onNavigate(selected.destination!)}
                    rightIcon={<ExternalLink className="w-4 h-4" />}
                  >
                    Bo‘limga o‘tish
                  </Button>
                )}
              </div>
            </Card>
            <div className="flex justify-between gap-3">
              <Button
                variant="outline"
                size="sm"
                disabled={selectedIndex <= 0}
                leftIcon={<ArrowLeft className="w-4 h-4" />}
                onClick={() => select(filtered[selectedIndex - 1].id)}
              >
                Oldingi mavzu
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={selectedIndex >= filtered.length - 1}
                rightIcon={<ArrowRight className="w-4 h-4" />}
                onClick={() => select(filtered[selectedIndex + 1].id)}
              >
                Keyingi mavzu
              </Button>
            </div>
          </article>
        </div>
      )}
      <Modal
        isOpen={Boolean(zoom)}
        onClose={() => setZoomId(null)}
        title={zoom?.title}
        description="Namunani yon tomonga surib belgilarni batafsil ko‘ring."
        size="2xl"
      >
        {zoom && (
          <div
            className="overflow-auto rounded-xl border border-slate-200"
            tabIndex={0}
            aria-label="Kattalashtirilgan namuna"
          >
            <div className="min-w-[1000px]"><GuidePreview scene={zoom.scene} description={zoom.previewAlt} zoom /></div>
          </div>
        )}
      </Modal>
    </div>
  );
}
