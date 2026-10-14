import { useEffect, useId, useRef, useState } from "react";
import { CalendarDays } from "lucide-react";
import { Input, type InputProps } from "./Input";
import { formatDate, formatMonth } from "../lib/dates";

type CalendarKind = "date" | "month";
export interface CalendarInputProps extends Omit<InputProps, "type" | "value" | "onChange" | "min" | "max"> {
  type?: CalendarKind;
  value: string;
  onValueChange: (value: string) => void;
  min?: string;
  max?: string;
  onValidityChange?: (valid: boolean) => void;
}

const calendarText = (iso: string, type: CalendarKind) => iso
  ? (type === "date" ? formatDate(iso) : formatMonth(iso)) : "";

export function parseCalendarInput(text: string, type: CalendarKind): string | null {
  const match = text.match(type === "date" ? /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/ : /^(\d{1,2})\.(\d{4})$/);
  if (!match) return null;
  const iso = type === "date"
    ? `${match[3]}-${match[2].padStart(2, "0")}-${match[1].padStart(2, "0")}`
    : `${match[2]}-${match[1].padStart(2, "0")}`;
  return (type === "date" ? formatDate(iso) : formatMonth(iso)) === "—" ? null : iso;
}

/** Editable local format with the platform calendar; parents receive only valid ISO or empty. */
export function CalendarInput({ type = "date", value, onValueChange, min, max, label,
  id, disabled, readOnly, error, onBlur, rightAddon, onValidityChange, ...props }: CalendarInputProps) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const picker = useRef<HTMLInputElement>(null);
  const emitted = useRef(value);
  const [text, setText] = useState(() => calendarText(value, type));
  const [touched, setTouched] = useState(false);
  const [rejected, setRejected] = useState(false);
  useEffect(() => {
    if (value !== emitted.current) {
      setText(calendarText(value, type)); setTouched(false); setRejected(false);
      emitted.current = value; onValidityChange?.(true);
    }
  }, [value, type, text, onValidityChange]);
  const parsed = parseCalendarInput(text, type);
  const bounded = parsed !== null && (!min || parsed >= min) && (!max || parsed <= max);
  const invalid = text === "" ? Boolean(props.required) : !bounded;
  const validation = invalid && touched ? (type === "date"
    ? "Sanani kun.oy.yil shaklida, ruxsat etilgan oraliqda kiriting."
    : "Oyni oy.yil shaklida, ruxsat etilgan oraliqda kiriting.") : undefined;
  const emit = (iso: string) => {
    emitted.current = iso;
    if (iso !== value) onValueChange(iso);
  };
  const calendarLabel = `${label || props["aria-label"] || "Sana"} — kalendar`;
  return <>
    <Input {...props} id={inputId} label={label} value={text} type="text"
      disabled={disabled} readOnly={readOnly} inputMode="decimal" autoComplete="off"
      placeholder={type === "date" ? "kun.oy.yil" : "oy.yil"}
      error={error || validation || (rejected ? "Noto‘g‘ri qiymat qabul qilinmadi. Oldingi tanlov saqlandi." : undefined)} aria-invalid={Boolean(error || invalid)}
      onChange={(event) => {
        const next = event.target.value.replace(/,/g, ".");
        setText(next); setTouched(true); setRejected(false);
        const iso = parseCalendarInput(next, type);
        const valid = iso !== null && (!min || iso >= min) && (!max || iso <= max);
        onValidityChange?.(next === "" ? !props.required : valid);
        if (next === "" && !props.required) emit("");
        else if (valid && iso) emit(iso);
      }}
      onBlur={(event) => {
        setTouched(true);
        if (bounded && parsed) setText(calendarText(parsed, type));
        else if (invalid) { setText(calendarText(value, type)); setRejected(true); onValidityChange?.(true); }
        onBlur?.(event);
      }}
      rightAddon={<>{rightAddon}<button type="button" disabled={disabled || readOnly}
        aria-label={calendarLabel} className="pointer-events-auto rounded p-1 text-slate-500 hover:text-blue-600 focus-visible:outline-2 focus-visible:outline-blue-500 disabled:opacity-40"
        onClick={() => {
          const element = picker.current;
          if (!element) return;
          if (typeof element.showPicker === "function") element.showPicker();
          else { element.focus(); element.click(); }
        }}><CalendarDays className="h-4 w-4" /></button></>} />
    <input ref={picker} type={type} tabIndex={-1} aria-hidden="true" className="sr-only"
      disabled={disabled || readOnly} value={value} min={min} max={max}
      onChange={(event) => {
        const iso = event.target.value;
        if (!iso && props.required) return;
        const valid = !iso || !(min && iso < min || max && iso > max);
        if (!valid) return;
        setText(calendarText(iso, type)); setTouched(false); setRejected(false);
        onValidityChange?.(true); emit(iso);
      }} />
  </>;
}
