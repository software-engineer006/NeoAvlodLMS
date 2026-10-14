import type { GuideScene, SceneField, SceneRegion } from "./types";

export const field = (label: string, value?: string): SceneField => ({ label, value });
export const choice = (label: string, ...options: string[]): SceneField => ({ label, options });
export const scene = (title: string, ...regions: SceneRegion[]): GuideScene => ({ title, regions });
export const groupDate: SceneRegion = { fields: [choice("Guruhni tanlang", "English A"),
  { label: "Dars sanasi", type: "date", value: "2026-10-14" }] };
export const marks: SceneRegion = { table: { columns: ["O‘quvchi", "Holat", "Izoh"],
  rows: [["Namuna O‘quvchi", "Keldi", "—"]] }, buttons: ["Keldi", "Kech qoldi", "Kelmadi"] };
export const summary: SceneRegion = { stats: [{ label: "Keldi", value: "1" },
  { label: "Kelmadi", value: "0" }, { label: "Belgilanmagan", value: "0" }] };
export const commonScenes = {
  login: scene("Panelga kirish", { fields: [field("Login", "namuna_xodim")] },
    { fields: [{ label: "Parol", type: "password", placeholder: "Shaxsiy parolingiz" }] }, { buttons: ["Kirish"] }),
  otp: scene("Telegram tasdiqlash kodi", { fields: [field("6 xonali tasdiqlash kodi")] },
    { note: "Kod 3 daqiqa amal qiladi. Kodni boshqa odamga bermang." }, { buttons: ["Tasdiqlash", "Qayta kod olish"] }),
  profile: scene("Mening profilim", { badges: ["Profilim"] },
    { fields: [field("Ism", "Namuna"), field("Familiya", "Xodim"), field("Login", "namuna_xodim")], buttons: ["Rasm tanlash"] },
    { buttons: ["Saqlash"] }),
  password: scene("Parolni yangilash", { fields: [{ label: "Eski parol", type: "password" }] },
    { fields: [{ label: "Yangi parol", type: "password" }, { label: "Parolni qayta kiriting", type: "password" }] },
    { buttons: ["Parolni yangilash"], note: "Yangilagach, yangi parol va Telegram kodi bilan qayta kiring." }),
  history: scene("Oylik davomat tarixi", { fields: [choice("Guruh", "English A")] },
    { fields: [field("Oy", "2026-10")] }, { table: { columns: ["O‘quvchi", "05.10", "07.10", "09.10"],
      rows: [["Namuna O‘quvchi", "Keldi", "Kech qoldi", "Kelmadi"]] } }),
};
