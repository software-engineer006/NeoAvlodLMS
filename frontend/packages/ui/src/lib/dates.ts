/** Calendar values stay ISO on the wire; every portal clock uses Tashkent. */
const clock = /* @__PURE__ */ new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Tashkent", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
});

function calendarParts(value: string): string[] | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split("-").map(Number);
  const check = new Date(`${value}T00:00:00Z`);
  return year >= 1 && check.getUTCFullYear() === year && check.getUTCMonth() + 1 === month
    && check.getUTCDate() === day ? value.split("-") : null;
}

function parts(value: string | Date) {
  // A legacy timestamp without an offset denotes UTC, never the browser zone.
  const normalized = typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(value)
    ? `${value}Z` : value;
  const date = normalized instanceof Date ? normalized : new Date(normalized);
  if (Number.isNaN(date.getTime())) return null;
  if (typeof value === "string" && !calendarParts(value.slice(0, 10))) return null;
  return Object.fromEntries(clock.formatToParts(date).map(part => [part.type, part.value]));
}

export function formatDate(value: string): string {
  if (!value.includes("T")) return calendarParts(value)?.reverse().join(".") ?? "—";
  const p = parts(value);
  return p ? `${p.day}.${p.month}.${p.year}` : "—";
}
export function formatDateTime(value: string): string {
  const p = parts(value);
  return p ? `${p.day}.${p.month}.${p.year} ${p.hour}:${p.minute}:${p.second}` : "—";
}
export function formatTime(value: string): string {
  const p = parts(value);
  return p ? `${p.hour}:${p.minute}:${p.second}` : "—";
}
export function formatExactDateTime(value: string): string {
  const text = formatDateTime(value);
  const fraction = value.match(/\.(\d+)(?:Z|[+-]\d\d:\d\d)?$/)?.[1];
  return text === "—" ? text : `${text}${fraction ? `.${fraction}` : ""}`;
}
export function tashkentToday(now = new Date()): string {
  const p = parts(now);
  return p ? `${p.year}-${p.month}-${p.day}` : "";
}
export const tashkentMonth = (now = new Date()) => tashkentToday(now).slice(0, 7);
export function formatMonth(value: string): string {
  return /^\d{4}-(0[1-9]|1[0-2])$/.test(value) && Number(value.slice(0, 4)) >= 1
    ? value.split("-").reverse().join(".") : "—";
}
export function shiftMonth(value: string, offset: number): string {
  if (formatMonth(value) === "—") return value;
  const date = new Date(`${value}-01T00:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() + offset);
  const next = `${String(date.getUTCFullYear()).padStart(4, "0")}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
  return formatMonth(next) === "—" ? value : next;
}
