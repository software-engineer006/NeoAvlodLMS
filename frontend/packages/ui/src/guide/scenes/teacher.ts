import { commonScenes, field, groupDate, marks, scene, summary } from "./common";

export const teacherScenes = {
  ...commonScenes,
  groups: scene("Mening guruhlarim", { table: { columns: ["Guruh", "Fan", "O‘quvchilar"], rows: [["English A", "English", "12"]] } },
    { badges: ["Dushanba", "Chorshanba", "Juma"], note: "Dars vaqti: 09:00–10:30. Xona: 101." },
    { buttons: ["O‘quvchilar", "Davomat olish"] }),
  students: scene("Guruh o‘quvchilari", { table: { columns: ["O‘quvchi", "Holat"], rows: [["Namuna O‘quvchi", "Faol"]] }, buttons: ["Profilni ochish"] },
    { fields: [field("Oy", "10.2026")], stats: [{ label: "Keldi", value: "3" }, { label: "Kech qoldi", value: "1" }, { label: "Kelmadi", value: "1" }] },
    { note: "Ota-ona kontakti faqat mavjud va o‘z guruhingizga tegishli bo‘lsa ko‘rinadi." }),
  draft: scene("Davomat belgilash", groupDate, { ...marks, fields: [field("Izoh", "Darsda")] },
    { buttons: ["Qoralama saqlash"], note: "Mavjud status yoki izohni tahrir qilsangiz, tuzatish sababini yozing." },
    { ...summary, buttons: ["Davomatni yakunlash"] }),
  finalize: scene("Davomatni yakunlash", summary, { buttons: ["Davomatni yakunlash"] },
    { buttons: ["Tasdiqlash va yakunlash"], note: "Ulangan ota-onalarga bildirishnomalar yuborish navbatiga qo‘yiladi." }),
  correction: scene("Yakunlangan davomatni tuzatish", { note: "Tahrirlash muddati: dars kunidan keyingi 2-kun 23:59:59 (Toshkent vaqti)." },
    { ...marks, fields: [field("Tuzatish sababi", "Jurnal qayta tekshirildi")] },
    { buttons: ["Tuzatishni saqlash"], note: "Yakunlangan holat saqlanadi. Tuzatish va sababi qayd etiladi." }),
};
