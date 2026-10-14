import { teacherScenes } from "./scenes/teacher";
import type { GuideTopic } from "./types";
const steps = (...values: [string, string][]) =>
  values.map(([title, text]) => ({ title, text }));
export const teacherTopics: GuideTopic[] = [
  {
    id: "teacher-login",
    title: "Hisobni Telegramga ulash va kirish",
    section: "Boshlash",
    summary:
      "Shaxsiy bot ulanishi, login va parol orqali teacher paneliga kiring.",
    scene: teacherScenes.login,
    previewAlt:
      "Teacher kirish ekranida login, parol va Kirish tugmasi raqamlangan.",
    steps: steps(
      [
        "Shaxsiy login",
        "Administrator yaratgan teacher hisobining bot havolasini Telegramda ochib Start bosing. Bot login va vaqtinchalik parolni beradi; loginni birinchi maydonga yozing.",
      ],
      [
        "Parol",
        "Shaxsiy parolingizni kiriting. Ko‘z belgisi bilan xatoni tekshirish mumkin; login/parolni boshqaga bermang.",
      ],
      [
        "Kirish",
        "Kirishni bosing. Telegramdagi 6 xonali kod keyingi bosqichda tasdiqlanadi. Teacher hisobidan admin portaliga kirib bo‘lmaydi.",
      ],
    ),
    tips: [
      "Botga boshqa Telegram hisobini ulab qo‘ymang. Yangi botga o‘tilsa administrator bergan yangi shaxsiy havolada yana Start bosish talab qilinadi.",
    ],
  },
  {
    id: "teacher-otp",
    title: "3 daqiqalik kod va 7 kun kirish",
    section: "Boshlash",
    summary:
      "Kodni tasdiqlang; sessiya davomida access yangilanishi avtomatik ishlaydi.",
    scene: teacherScenes.otp,
    previewAlt:
      "Teacher OTP ekranida kod maydoni, uch daqiqalik taymer va Tasdiqlash belgilangan.",
    steps: steps(
      [
        "Kodni kiriting",
        "Telegram bot yuborgan ayni kirish uchun 6 xonali kodni yozing. Parol tiklash kodi boshqa maqsad uchun ishlatiladi.",
      ],
      [
        "Taymerni tekshiring",
        "Kod 3 daqiqa amal qiladi va bir marta ishlatiladi. 00:00 yoki urinishlar limiti bo‘lsa yangi kod so‘rang.",
      ],
      [
        "Tasdiqlang",
        "Tasdiqlashdan keyin sessiya ko‘pi bilan 7 kun davom etadi. Qisqa access tugaganda tizim davomat so‘rovini avtomatik yangilangan sessiya bilan takrorlaydi; tanlov va izoh yo‘qolmaydi.",
      ],
    ),
    tips: [
      "Chiqish/parolni yangilash/hisobni faolsiz qilish sessiyani oldinroq bekor qiladi. 7 kun tugasa yana login va kod kerak.",
      "Kod kelmasa shaxsiy bot ulanishi va internetni tekshiring; yangi kod oling. Tarmoq xatosida formani yopishga shoshilmang.",
    ],
  },
  {
    id: "teacher-groups",
    title: "Mening guruhlarim va dars jadvali",
    section: "Guruhlar",
    destination: "groups",
    summary: "Faqat sizga biriktirilgan guruhlar, jadval va sig‘imni ko‘ring.",
    scene: teacherScenes.groups,
    previewAlt:
      "Teacher guruh jadvalida jadval, o‘quvchilar ro‘yxati va davomatga o‘tish belgilangan.",
    steps: steps(
      [
        "Guruh jadvali",
        "Mening guruhlarimda fan, dars kunlari, vaqt, xona va o‘quvchilar sonini tekshiring. Vaqt Toshkent mahalliy vaqti.",
      ],
      [
        "O‘quvchilarni oching",
        "guruh ro‘yxatidagi o‘quvchilar ro‘yxati tugmasi shu guruhdagi profil va ota-ona ma’lumotlarini ochadi.",
      ],
      [
        "Davomatga o‘ting",
        "Guruh ro‘yxatidagi davomat tugmasi ayni guruhni oldindan tanlaydi. Menyudagi Davomat olish orqali boshqa o‘z guruhingizni ham tanlash mumkin.",
      ],
    ),
    tips: [
      "Guruh ko‘rinmasa administrator sizni teacher sifatida biriktirganini tekshirsin. Begona guruh/o‘quvchi havolasi ochilmaydi.",
    ],
  },
  {
    id: "teacher-students",
    title: "O‘quvchi profili va oylik statistika",
    section: "Guruhlar",
    destination: "groups",
    summary:
      "O‘z guruhingiz o‘quvchilari, ota-ona va oylik qatnashuvini ko‘ring.",
    scene: teacherScenes.students,
    previewAlt:
      "Teacher o‘quvchi profilida ism, ota-ona/guruh va davomat statistikasi raqamlangan.",
    steps: steps(
      [
        "Profilni oching",
        "Guruhning o‘quvchilar ro‘yxatidan kerakli o‘quvchining batafsil profilini oching.",
      ],
      [
        "Ma’lumotlarni tekshiring",
        "O‘quvchi, ota-ona, guruh/jadval va Telegram ulanish holatini ko‘ring. Noma’lum telefon/yosh/sinf alohida kiritilmagan deb ko‘rsatiladi.",
      ],
      [
        "Oy va statistika",
        "Oy tanlovini almashtirib keldi, kechikdi, kelmadi soni hamda jami yakunlangan darslar/foizni solishtiring.",
      ],
    ),
    tips: [
      "Teacher profilni o‘qiydi; o‘quvchini yaratish, ko‘chirish yoki aloqa ma’lumotini tahrirlash administrator orqali amalga oshiriladi.",
      "Bo‘sh davomat absent degani emas; administrator aniqlashtirmaguncha taxmin bilan belgilanmaydi.",
    ],
  },
  {
    id: "teacher-draft",
    title: "Davomat belgilash va qoralama",
    section: "Davomat",
    destination: "attendance",
    summary: "Guruh/sana bo‘yicha o‘quvchi statusi va izohni xavfsiz saqlang.",
    scene: teacherScenes.draft,
    previewAlt:
      "Teacher davomatida guruh/sana, statuslar, qoralama va yakunlash tugmalari raqamlangan.",
    steps: steps(
      [
        "Guruh va sana",
        "Davomat olishda guruh va dars sanasini tanlang. Kelajak sanasi yoki yozish muddati yopilgan sana uchun tahrir ishlamaydi.",
      ],
      [
        "Status va izoh",
        "Har bir faol o‘quvchini Keldi, Kech qoldi yoki Kelmadi deb belgilang. Zarur izohni yozing; Hammani keldi amalidan keyin ham ro‘yxatni tekshiring.",
      ],
      [
        "Qoralama saqlash",
        "Qoralama saqlashni bosing. Mavjud status yoki izohni o‘zgartirsangiz, Tuzatish sababi maydonini to‘ldiring. Statuslar saqlanadi, dars yakunlanmaydi va Telegram notification yuborilmaydi.",
      ],
      [
        "Yakunlashga tayyorlang",
        "Barcha o‘quvchilar belgilanganini tekshiring; Davomatni yakunlash keyingi mavzudagi tasdiqni ochadi.",
      ],
    ),
    tips: [
      "Guruh/sana almashganda saqlanmagan o‘zgarishlar haqida ogohlantirish chiqadi: saqlang yoki ongli ravishda bekor qiling.",
      "Internet uzilsa qoralama va tanlovni saqlab qayta urinib ko‘ring.",
    ],
  },
  {
    id: "teacher-finalize",
    title: "Davomatni yakunlash va bildirishnomalar",
    section: "Davomat",
    destination: "attendance",
    summary: "To‘liq belgilangan darsni bir marta tasdiqlab yakunlang.",
    scene: teacherScenes.finalize,
    previewAlt:
      "Teacher yakunlash modalida status sonlari, bildirishnoma izohi va yakunlash tasdig‘i raqamlangan.",
    steps: steps(
      [
        "Statuslarni tekshiring",
        "Davomatni yakunlash tugmasidan keyin modalda sana/guruh va keldi/kelmadi/kechikdi sonlarini solishtiring.",
      ],
      [
        "Bildirishnoma tartibi",
        "Yakunlash davomat va bot xabarlari navbatini bir tranzaksiyada saqlaydi. Faqat tegishli ulangan ota-onalarga notification yetkaziladi.",
      ],
      [
        "Yakunlashni tasdiqlang",
        "Tasdiq tugmasini bosing va muvaffaqiyat holatini kuting. Bir dars qayta yakunlanganda ikkinchi batch yaratilmaydi.",
      ],
    ),
    tips: [
      "Belgilanmagan o‘quvchi bo‘lsa yakunlash yopiq. Internet/bot yetkazish xatosi yakunlangan davomatni yo‘qotmaydi; worker navbatni qayta urinadi.",
    ],
  },
  {
    id: "teacher-correction",
    title: "Yakunlangan davomatni 2 kun ichida tuzatish",
    section: "Davomat",
    destination: "attendance",
    summary: "O‘z guruhingizdagi xatoni muddat tugamasdan tuzating.",
    scene: teacherScenes.correction,
    previewAlt:
      "Teacher yakunlangan darsida tahrir muddati, status va tuzatishni saqlash raqamlangan.",
    steps: steps(
      [
        "Muddatni tekshiring",
        "Dars sanasidan keyingi ikkinchi kunning oxirigacha, Asia/Tashkent vaqti bilan yozish mumkin. Masalan dushanba darsi chorshanba 23:59 gacha; muddat tugasa status tugmalari yopiladi.",
      ],
      [
        "Status/izohni to‘g‘rilang",
        "Ayni guruh va sanada kerakli o‘quvchi statusi yoki izohini tuzating va Tuzatish sababi maydonini to‘ldiring. Guruh sizga biriktirilgan bo‘lishi kerak.",
      ],
      [
        "Tuzatishni saqlang",
        "Tuzatishni saqlash bosing. Dars yakunlangan holatda qoladi, eski/yangi qiymat, sabab va muallif logda saqlanadi. Logni faqat superadmin ko‘radi.",
      ],
    ),
    tips: [
      "Muddatdan keyin tarixni o‘qish mumkin, yozish uchun administratorga to‘g‘ri status va sabab bilan murojaat qiling. Administrator eski sanani ham audit sababi bilan tuzatadi.",
    ],
  },
  {
    id: "teacher-history",
    title: "Guruh va oy bo‘yicha davomat tarixi",
    section: "Davomat",
    destination: "history",
    summary:
      "O‘z guruhingizning to‘liq oy jadvali va jami qatnashuvini tekshiring.",
    scene: teacherScenes.history,
    previewAlt:
      "Teacher tarixida guruh, oy tanlovi va davomat matritsasi belgilangan.",
    steps: steps(
      ["Guruhni tanlang", "Davomat tarixi menyusida o‘z guruhingizni tanlang."],
      [
        "Oyni tanlang",
        "Oy maydoni yoki Oldingi/Keyingi oy orqali vaqt oralig‘ini almashtiring.",
      ],
      [
        "Matritsani o‘qing",
        "Keldi/kechikdi/kelmadi rang va belgilar bilan ko‘rsatiladi; bo‘sh katak belgilanmagan. Keng jadvalni yon tomonga surish va o‘quvchi profilini ochish mumkin.",
      ],
    ),
    tips: [
      "Tarix eski oylar uchun ham ochiq. Teacher faqat o‘z guruhidagi ma’lumotni ko‘radi; administrator tahriri shu tarixda ham aks etadi.",
    ],
  },
  {
    id: "teacher-profile",
    title: "Shaxsiy profil va rasm",
    section: "Hisob",
    summary: "O‘z ism/telefon/login va profil rasmingizni yangilang.",
    scene: teacherScenes.profile,
    previewAlt:
      "Teacher profil modalida rasm yuklash, login/ma’lumotlar va Saqlash belgilangan.",
    steps: steps(
      [
        "Rasm",
        "Yuqoridagi Profilimni oching. Rasm yuklash/almashtirish/o‘chirish amali bor; ekrandagi tur/hajm talabini tekshiring.",
      ],
      [
        "Shaxsiy ma’lumotlar",
        "Ism, familiya, login va telefonni tekshiring. Noma’lum qiymatni uydirmang; telefon xalqaro formatda.",
      ],
      [
        "Saqlang",
        "Saqlashni bosing. Bot qayta ulanish kerakligini ko‘rsatsa administratordan yangi shaxsiy havola oling va Start bosing.",
      ],
    ),
    tips: [
      "Faqat o‘z profilingiz tahrirlanadi. Rol, guruh biriktirish va administrator ruxsatlarini teacher o‘zgartirmaydi.",
    ],
  },
  {
    id: "teacher-password",
    title: "Parolni yangilash yoki tiklash",
    section: "Hisob",
    summary:
      "Vaqtinchalik parolni almashtiring; unutilgan parolni Telegram bilan tiklang.",
    scene: teacherScenes.password,
    previewAlt:
      "Teacher parol formasida joriy parol, yangi parol va O‘zgartirish belgilangan.",
    steps: steps(
      [
        "Joriy parol",
        "Paneldagi Parol yoki Profilim → Xavfsizlik va parolni oching. Eski parolni kiriting.",
      ],
      [
        "Yangi parol",
        "Formadagi murakkablik talabiga mos yangi parol va tasdiqni bir xil yozing.",
      ],
      [
        "O‘zgartiring",
        "O‘zgartirishni bosing. Eski sessiyalar yopiladi; yangi parol va Telegram kodi bilan yana kiring.",
      ],
    ),
    tips: [
      "Parol unutilsa login sahifasidagi Parolni unutdingizmi?dan foydalaning: login → 3 daqiqalik Telegram kod → yangi parol. Kod login maqsadi bilan aralashtirilmaydi.",
    ],
  },
];
