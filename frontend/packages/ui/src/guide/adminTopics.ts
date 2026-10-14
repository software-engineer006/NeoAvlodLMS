import { PERMISSIONS as P } from "../navigation/permissions";
import type { GuideTopic } from "./types";

const images = {
  login: /* @__PURE__ */ new URL("./images/admin-login.png", import.meta.url).href,
  otp: /* @__PURE__ */ new URL("./images/admin-otp.png", import.meta.url).href,
  profile: /* @__PURE__ */ new URL("./images/admin-profile.png", import.meta.url).href,
  password: /* @__PURE__ */ new URL("./images/admin-password.png", import.meta.url).href,
  dashboard: /* @__PURE__ */ new URL("./images/admin-dashboard.png", import.meta.url).href,
  staff: /* @__PURE__ */ new URL("./images/admin-staff.png", import.meta.url).href,
  grants: /* @__PURE__ */ new URL("./images/admin-grants.png", import.meta.url).href,
  subjects: /* @__PURE__ */ new URL("./images/admin-subjects.png", import.meta.url).href,
  groups: /* @__PURE__ */ new URL("./images/admin-groups.png", import.meta.url).href,
  groupForm: /* @__PURE__ */ new URL("./images/admin-group-form.png", import.meta.url).href,
  students: /* @__PURE__ */ new URL("./images/admin-students.png", import.meta.url).href,
  studentStats: /* @__PURE__ */ new URL("./images/admin-student-stats.png", import.meta.url)
    .href,
  studentForm: /* @__PURE__ */ new URL("./images/admin-student-form.png", import.meta.url).href,
  studentEdit: /* @__PURE__ */ new URL("./images/admin-student-edit.png", import.meta.url).href,
  history: /* @__PURE__ */ new URL("./images/admin-history.png", import.meta.url).href,
  audit: /* @__PURE__ */ new URL("./images/admin-audit.png", import.meta.url).href,
  attendance: /* @__PURE__ */ new URL("./images/admin-attendance.png", import.meta.url).href,
  correction: /* @__PURE__ */ new URL("./images/admin-correction.png", import.meta.url).href,
  messages: /* @__PURE__ */ new URL("./images/admin-messages.png", import.meta.url).href,
  delivery: /* @__PURE__ */ new URL("./images/admin-delivery.png", import.meta.url).href,
  bot: /* @__PURE__ */ new URL("./images/admin-bot.png", import.meta.url).href,
};
const steps = (...values: [string, string][]) =>
  values.map(([title, text]) => ({ title, text }));

export const adminTopics: GuideTopic[] = [
  {
    id: "admin-login",
    title: "Telegram orqali kirish",
    section: "Boshlash",
    summary: "Shaxsiy login, parol va Telegram kodi bilan panelga kiring.",
    image: images.login,
    imageAlt:
      "Admin kirish ekranida login, parol va kirish tugmasi raqamlar bilan belgilangan.",
    steps: steps(
      [
        "Loginni yozing",
        "Xodim hisobiga berilgan foydalanuvchi nomini kiriting. Telefon raqami o‘rniga login ishlatiladi.",
      ],
      [
        "Parolni kiriting",
        "Shaxsiy parolni yozing; ko‘z belgisi bilan vaqtincha ko‘rish mumkin. Hisob egasi avval administrator bergan bot havolasida Start bosgan bo‘lishi kerak.",
      ],
      [
        "Kirishni bosing",
        "Tizim Telegram botga tasdiqlash kodini yuboradi. Keyingi mavzuda kodni kiritish tartibi ko‘rsatilgan.",
      ],
    ),
    tips: [
      "Kod kelmasa botga to‘g‘ri Telegram hisobingiz orqali ulanganingizni tekshiring. Kodni boshqalarga bermang.",
      "Admin portaliga teacher hisobi bilan kirib bo‘lmaydi.",
    ],
  },
  {
    id: "admin-otp",
    title: "3 daqiqalik kod va 7 kunlik sessiya",
    section: "Boshlash",
    summary: "Kodni vaqtida tasdiqlang; kundalik qayta login talab qilinmaydi.",
    image: images.otp,
    imageAlt:
      "Tasdiqlash ekranida 6 xonali kod, uch daqiqalik taymer va tasdiqlash belgilangan.",
    steps: steps(
      [
        "Kod maydoni",
        "Telegramdan kelgan ayni kirish uchun 6 xonali kodni yozing. Parol tiklash kodi kirish kodidan alohida.",
      ],
      [
        "Muddatni tekshiring",
        "Kod 3 daqiqa amal qiladi va bir marta ishlatiladi. Taymer 00:00 bo‘lsa yangi kod so‘rang; ko‘p xato urinishdan keyin ham yangi kod kerak.",
      ],
      [
        "Tasdiqlang",
        "Muvaffaqiyatli kirishdan keyin sessiya ko‘pi bilan 7 kun davom etadi. Qisqa access muddati tugaganda tizim uni avtomatik yangilaydi.",
      ],
    ),
    tips: [
      "Chiqish, parolni o‘zgartirish/tiklash yoki hisobni o‘chirish sessiyani oldinroq bekor qiladi.",
      "7 kun tugasa qayta kiring. Internet xatosida yozilgan formani saqlab, so‘rovni qayta urinib ko‘ring.",
    ],
  },
  {
    id: "admin-dashboard",
    title: "Panel va bo‘limlar bilan tanishish",
    section: "Boshlash",
    summary: "Menyu, statistikalar va shaxsiy profil joylashuvini bilib oling.",
    image: images.dashboard,
    imageAlt:
      "Admin panel menyusi, boshqaruv kartalari va Profilim tugmasi belgilangan.",
    destination: "dashboard",
    steps: steps(
      [
        "Menyudan foydalaning",
        "Chap menyuda faqat hisobingizga ochiq bo‘limlar turadi. Kichik ekranda yuqoridagi menyu belgisini bosing.",
      ],
      [
        "Panelni ko‘zdan kechiring",
        "Dashboardda ruxsatli statistika va joriy hisob ma’lumotlari ko‘rsatiladi. Ruxsat berilmagan modulning sonlari ochilmaydi.",
      ],
      [
        "Profilni oching",
        "Yuqoridagi Profilim orqali o‘z ma’lumotlaringizni, bot ulanishini va parolingizni boshqarasiz.",
      ],
    ),
    tips: [
      "Yangi ruxsatlar panelga qaytganda yoki faol oynada bir daqiqada yangilanadi. Backend har bir amalning ruxsatini darhol tekshiradi.",
    ],
  },
  {
    id: "admin-profile",
    title: "Shaxsiy profil va rasm",
    section: "Hisob",
    summary: "Ism, aloqa ma’lumotlari va profil rasmini yangilang.",
    image: images.profile,
    imageAlt:
      "Profil modalida rasm, shaxsiy ma’lumotlar va saqlash tugmasi belgilangan.",
    steps: steps(
      [
        "Profil rasmini tanlang",
        "Profilimni ochib rasm yuklash yoki o‘chirish amalidan foydalaning. Formadagi tur va hajm talabiga rioya qiling.",
      ],
      [
        "Ma’lumotlarni to‘ldiring",
        "Ism, familiya, telefon va loginni tekshirib tahrirlang. Telefon xalqaro formatda kiritiladi; login kichik lotin harflari, raqam va pastki chiziqdan iborat.",
      ],
      [
        "O‘zgarishlarni saqlang",
        "Saqlashni bosing, muvaffaqiyat xabarini tekshiring. Telegram holati qayta ulanish kerakligini bildirsa administrator yoki superadmindan yangi ulanish havolasini oling va Start bosing.",
      ],
    ),
    tips: [
      "Bu bo‘lim o‘z profilingiz uchun. Boshqa xodimni boshqarish alohida ruxsatga bog‘liq.",
    ],
  },
  {
    id: "admin-password",
    title: "Parolni o‘zgartirish va tiklash",
    section: "Hisob",
    summary:
      "Amaldagi parolni yangilang yoki unutilgan parolni Telegram kodi bilan tiklang.",
    image: images.password,
    imageAlt:
      "Parol formasida joriy parol, yangi parol va saqlash belgilangan.",
    steps: steps(
      [
        "Joriy parolni yozing",
        "Paneldagi Parol tugmasini yoki profilning parol bo‘limini oching. Joriy parolingizni kiriting.",
      ],
      [
        "Yangi parol va tasdiq",
        "Formadagi murakkablik talabiga mos yangi parolni ikki maydonga bir xil yozing. Ko‘z belgisi xatoni tekshirishga yordam beradi.",
      ],
      [
        "Saqlang va qayta kiring",
        "Parol yangilanganda eski sessiyalar bekor qilinadi; yangi parol bilan qayta kirish kerak.",
      ],
    ),
    tips: [
      "Parol unutilsa kirish sahifasidagi Parolni unutdingizmi? orqali loginni yozing, Telegramdagi 3 daqiqalik kodni tasdiqlang va yangi parol qo‘ying.",
    ],
  },
  {
    id: "admin-staff",
    title: "O‘qituvchi hisobini yaratish va boshqarish",
    section: "Xodimlar",
    permission: P.STAFF_MANAGE,
    destination: "staff",
    summary: "Teacher hisobini oching, profil va faol holatini boshqaring.",
    image: images.staff,
    imageAlt:
      "Teacher yaratish formasida ism, login va yaratish tugmasi belgilangan; admin permission boshqaruvi ko‘rsatilmagan.",
    steps: steps(
      [
        "Xodim ma’lumotlari",
        "Xodimlar → Yangi xodim qo‘shish. Ismni yozing, mavjud bo‘lsa familiya va telefonni kiriting; noma’lum qiymatni uydirmang.",
      ],
      [
        "Loginni belgilang",
        "Takrorlanmaydigan kichik lotincha login tanlang. Administrator faqat teacher yaratadi; superadmin admin rolini ham tanlay oladi.",
      ],
      [
        "Yarating va ulang",
        "Yaratishdan so‘ng profilni oching va Telegram ulanish havolasini hisob egasiga bering. U Start bosganda bot login va vaqtinchalik parolni beradi.",
      ],
    ),
    tips: [
      "Admin staff:manage bilan faqat teacher hisobini tahrirlaydi/statusini boshqaradi. Admin va superadmin hisoblarini superadmin boshqaradi.",
      "Faolsiz xodim tizimga kira olmaydi. Davomat tarixi bor hisobni o‘chirish cheklanishi mumkin.",
    ],
  },
  {
    id: "admin-grants",
    title: "Administrator va barcha ruxsatlar",
    section: "Xodimlar",
    superadminOnly: true,
    destination: "staff",
    summary:
      "Administratorga kerakli amallarni yoki katalogdagi barcha ruxsatlarni bering.",
    image: images.grants,
    imageAlt:
      "Superadmin formasida Administrator roli, barcha ruxsatlar tugmasi va alohida checkboxlar belgilangan.",
    steps: steps(
      [
        "Administrator rolini tanlang",
        "Yangi xodim yaratishda Administratorni tanlang yoki mavjud administratorni tahrirlashni oching.",
      ],
      [
        "To‘liq ruxsat kerak bo‘lsa",
        "Barcha ruxsatlarni berish 11 ta katalog kalitini belgilaydi. Ruxsatlarni tozalash barcha kalitlarni olib tashlaydi.",
      ],
      [
        "Aniq amallarni belgilang",
        "Ko‘rish, yaratish va tahrirlash alohida tanlanadi. Yaratish/tahrirlash ko‘rishni ham beradi; ko‘rishni olib tashlash unga bog‘liq yozishlarni ham o‘chiradi.",
      ],
      [
        "Saqlang",
        "Hisobni saqlang. Administratorning menyusi va qo‘llanmasi berilgan ruxsatlarga mos yangilanadi.",
      ],
    ),
    tips: [
      "Full permission adminni superadmin roliga aylantirmaydi. Bot sozlamalari va administrator permissionlarini berish faqat superadmin uchun.",
      "Oxirgi faol superadminni faolsiz qilish/o‘chirish himoyalangan.",
    ],
  },
  {
    id: "admin-subjects",
    title: "Fan yaratish, tahrirlash va holati",
    section: "Ta’lim",
    permission: P.SUBJECTS_MANAGE,
    destination: "subjects",
    summary: "Fan katalogini boshqaring va guruhga biriktirishga tayyorlang.",
    image: images.subjects,
    imageAlt: "Fan formasida nom, izoh va yaratish tugmasi belgilangan.",
    steps: steps(
      [
        "Fan nomi",
        "Fanlar → Yangi fan. Tushunarli va takrorlanmaydigan nom kiriting.",
      ],
      [
        "Izoh",
        "Qo‘shimcha tavsif kerak bo‘lsa yozing. Keyin shu formadan tahrirlash ham mumkin.",
      ],
      [
        "Saqlang va holatini tekshiring",
        "Yaratish/Saqlashni bosing. Faolsiz fan yangi guruh tanlovida chiqmaydi; o‘chirish bog‘langan guruhlar bilan cheklanishi mumkin.",
      ],
    ),
    tips: [
      "Guruh yaratuvchi administratorga fan tanlash uchun subjects:manage berish shart emas; u minimal tanlovdan foydalanadi.",
    ],
  },
  {
    id: "admin-groups",
    title: "Guruhlarni topish va jadvalni ko‘rish",
    section: "Ta’lim",
    permission: P.GROUPS_READ,
    destination: "groups",
    summary:
      "Qidiruv, fan/teacher/kun va status filtrlari bilan kerakli guruhni toping.",
    image: images.groups,
    imageAlt:
      "Read-only guruh ekranida qidiruv, filtrlar va jadval belgilangan; yozish tugmalari yo‘q.",
    steps: steps(
      [
        "Ism bo‘yicha qidiring",
        "Guruh nomini yozing. Ro‘yxat qidiruvga mos yangilanadi; sahifalar orasida navigatsiya qiling.",
      ],
      [
        "Filtrlarni qo‘llang",
        "Fan, o‘qituvchi, hafta kuni va faol holati orqali ro‘yxatni toraytiring. Filtr natijasi bo‘sh bo‘lsa talablarni yumshating.",
      ],
      [
        "Jadval va sig‘imni tekshiring",
        "Dars kunlari, boshlanish/tugash vaqti, xona, teacher va band/sig‘im sonini ko‘ring.",
      ],
    ),
    tips: [
      "Faqat ko‘rish ruxsati guruh yaratish yoki tahrirlash tugmalarini ochmaydi. Dars jadvali Toshkent mahalliy vaqtida.",
    ],
  },
  {
    id: "admin-group-create",
    title: "Yangi guruh yaratish",
    section: "Ta’lim",
    permission: P.GROUPS_CREATE,
    destination: "groups",
    summary: "Fan, teacher, toq/juft kunlar va aniq dars vaqtini belgilang.",
    image: images.groupForm,
    imageAlt:
      "Guruh yaratish formasida nom, fan/teacher, dars kunlari va yaratish belgilangan.",
    steps: steps(
      [
        "Guruh nomi",
        "Guruhlar → Yangi guruh. Kurs va guruhni farqlaydigan nom yozing.",
      ],
      [
        "Fan va o‘qituvchini tanlang",
        "Faol fan va faol teacherni tanlang. Tanlovlar uchun xodim yoki fanlarni boshqarish granti shart emas.",
      ],
      [
        "Jadval va sig‘im",
        "Toq kunlar Dush/Chor/Jum, juft kunlar Sesh/Pay/Shan. Kerakli kunlar, boshlanish/tugash, xona, oylik narx va maksimal o‘quvchi sonini belgilang.",
      ],
      [
        "Yarating",
        "Vaqt tartibi va sig‘imni tekshirib Yaratish bosing. Noto‘g‘ri vaqt yoki faol bo‘lmagan teacher/fan serverda rad qilinadi.",
      ],
    ),
    tips: [
      "Yaratish ruxsati shu modulni ko‘rishni ham beradi; mavjud guruhni tahrirlash uchun alohida groups:edit kerak.",
    ],
  },
  {
    id: "admin-group-edit",
    title: "Guruhni tahrirlash va faolligi",
    section: "Ta’lim",
    permission: P.GROUPS_EDIT,
    destination: "groups",
    summary: "Mavjud guruh jadvali, teacheri va sig‘imini to‘g‘rilang.",
    image: images.groupForm,
    imageAlt:
      "Guruh formasida tahrirlanadigan nom, fan/teacher va jadval belgilangan; namuna yaratish formasi shu maydonlarni ko‘rsatadi.",
    steps: steps(
      [
        "Guruhni toping",
        "Guruhlar ro‘yxatidan kerakli guruhning tahrirlash belgisini bosing. Nom formaning birinchi maydonida turadi.",
      ],
      [
        "Biriktirishni tekshiring",
        "Fan yoki teacher o‘zgarsa davomat uchun yangi ownership keyingi so‘rovlarda amal qiladi.",
      ],
      [
        "Jadvalni to‘g‘rilang",
        "Dars kunlari, vaqti, xona va narx/sig‘imni yangilang. Sig‘im hozirgi faol o‘quvchilar sonidan kam bo‘la olmaydi.",
      ],
      [
        "Saqlang va holatini boshqaring",
        "Tahrirlashda tugma Saqlash bo‘ladi. Ro‘yxatdagi faollik amalidan foydalaning; bog‘langan yozuv bor guruhni o‘chirish serverda cheklanishi mumkin.",
      ],
    ),
    tips: [
      "O‘chirish tasdig‘ini diqqat bilan o‘qing. O‘quvchi va tarixni yo‘qotmaslik uchun zarur holatda guruhni faolsiz qiling.",
    ],
  },
  {
    id: "admin-students",
    title: "O‘quvchi, ota-ona va Telegram profili",
    section: "O‘quvchilar",
    permission: P.STUDENTS_READ,
    destination: "students",
    summary: "O‘quvchi, ota-ona, guruh va bot ulanish holatini ko‘ring.",
    image: images.students,
    imageAlt:
      "Read-only o‘quvchi profilida shaxsiy ma’lumotlar, guruh va Telegram holati belgilangan.",
    steps: steps(
      [
        "O‘quvchini oching",
        "O‘quvchilar ro‘yxatida ism/telefon/guruh orqali toping va profilni ochish belgisini bosing.",
      ],
      [
        "Ma’lumotlarni tekshiring",
        "Profil, ota-ona, guruh/jadvalni ko‘ring. Kiritilmagan ma’lumot bo‘sh deb ko‘rsatiladi.",
      ],
      [
        "Ulanish holati",
        "O‘quvchi va ota-onaning Telegram holati alohida ko‘rsatiladi. Ulanmagan hisob o‘z havolasi orqali botda Start bosishi kerak.",
      ],
    ),
    tips: [
      "Bo‘sh davomat avtomatik kelmadi degani emas. Tarixda belgilangan statusga qarang.",
      "Faqat read profilni ko‘rsatadi; tahrirlash/ko‘chirish/status/link yangilash uchun students:edit kerak.",
    ],
  },
  {
    id: "admin-student-stats",
    title: "O‘quvchining oylik davomat statistikasi",
    section: "O‘quvchilar",
    permission: P.STUDENTS_READ,
    requiresAll: [P.ATTENDANCE_READ],
    destination: "students",
    summary:
      "Profil va davomatni ko‘rish ruxsatlari bilan oylik qatnashuvni tahlil qiling.",
    image: images.studentStats,
    imageAlt:
      "O‘quvchi statistikasi ekranida oy tanlovi, davomat sonlari va foiz belgilangan.",
    steps: steps(
      [
        "Oyni tanlang",
        "O‘quvchi profilidagi statistikada kerakli oyga o‘ting. Oldingi/keyingi oy tugmalari va oy tanlovi ishlatiladi.",
      ],
      [
        "Status sonlari",
        "Keldi, kechikdi va kelmadi sonlarini tekshiring. Qatnashgan soni keldi va kechikdini birga hisoblaydi.",
      ],
      [
        "Umumiy dars va foiz",
        "Yakunlangan darslar va belgilanmagan kataklarni solishtiring. Bo‘sh katakni taxmin bilan absent deb hisoblamang.",
      ],
    ),
    tips: [
      "Bu mavzu students:read va attendance:read birga berilganda chiqadi.",
    ],
  },
  {
    id: "admin-student-create",
    title: "O‘quvchi va ota-onani qo‘shish",
    section: "O‘quvchilar",
    permission: P.STUDENTS_CREATE,
    destination: "students",
    summary:
      "Guruh sig‘imi doirasida o‘quvchi va ota-ona ma’lumotini birga saqlang.",
    image: images.studentForm,
    imageAlt:
      "Yangi o‘quvchi formasida o‘quvchi ma’lumotlari, guruh, ota-ona va yaratish belgilangan.",
    steps: steps(
      [
        "O‘quvchi maydonlari",
        "Yangi o‘quvchi tugmasini bosing. Ism, ma’lum bo‘lsa familiya, telefon va yoshni kiriting.",
      ],
      [
        "Guruhni tanlang",
        "Faol guruh bandligi va maksimal sonni tekshiring. To‘lgan guruhga qo‘shish serverda rad qilinadi.",
      ],
      [
        "Ota-ona ma’lumotlari",
        "Ota-onaning ism va aloqa ma’lumotlarini mavjud holatda yozing. Telefon bir xil bo‘lgani uchun turli ota-onalar avtomatik birlashtirilmaydi.",
      ],
      [
        "Ro‘yxatga oling",
        "Ro‘yxatga olishni bosing; keyin profil orqali o‘quvchi va ota-onaning alohida bot ulanish holatini tekshiring.",
      ],
    ),
    tips: [
      "Berilmagan ma’lumotni uydirmang. Ota-ona profili bo‘lmasa unga xabar auditoriyasi yaratilmaydi.",
    ],
  },
  {
    id: "admin-student-edit",
    title: "Profilni tahrirlash, ko‘chirish va Telegram",
    section: "O‘quvchilar",
    permission: P.STUDENTS_EDIT,
    destination: "students",
    summary:
      "Ma’lumotlarni to‘ldiring, guruhni almashtiring va bot ulanishini boshqaring.",
    image: images.studentEdit,
    imageAlt:
      "O‘quvchi profilida tahrirlash, guruhga ko‘chirish va Telegram ulanish amallari belgilangan.",
    steps: steps(
      [
        "Profilni tahrirlang",
        "O‘quvchi profilidan Tahrirlashni ochib mavjud ma’lumotlarni to‘g‘rilang va saqlang.",
      ],
      [
        "Guruhga ko‘chiring",
        "Ko‘chirishni tanlang, yangi faol guruh sig‘imini tekshirib tasdiqlang. Oldingi davomat tarixi saqlanadi.",
      ],
      [
        "Telegramni ulang",
        "Profilning o‘quvchi va ota-ona bo‘limidagi alohida havolalar orqali tegishli hisob egasi Start bosadi. Eskirgan havolani yangilash mavjud bog‘lanish qoidalariga bo‘ysunadi.",
      ],
      [
        "Faollikni boshqaring",
        "Faolsiz qilish/yoqish yoki o‘chirishda tasdiqni o‘qing. Faolsiz o‘quvchi yangi davomat/xabar auditoriyasiga kirmaydi; tarix bor o‘quvchini o‘chirish cheklanishi mumkin.",
      ],
    ),
    tips: [
      "Havola faqat tegishli shaxsga beriladi. Bitta Telegram hisobiga noto‘g‘ri odamni bog‘lamang.",
    ],
  },
  {
    id: "admin-history",
    title: "Oylik davomat va o‘zgarishlar tarixi",
    section: "Davomat",
    permission: P.ATTENDANCE_READ,
    destination: "attendance",
    summary: "Guruh/oy matritsasi, statuslar va kim o‘zgartirganini ko‘ring.",
    image: images.history,
    imageAlt: "Davomat tarixida guruh, oy va status kataklari belgilangan.",
    steps: steps(
      [
        "Guruhni tanlang",
        "Davomat → Oylik jadval (Guruh / Oy) bo‘limida kerakli guruhni tanlang. Admin ruxsati barcha guruhlarga tegishli.",
      ],
      [
        "Oyni belgilang",
        "Oy tanlovi yoki oldingi/keyingi oy tugmalari bilan davrni almashtiring.",
      ],
      [
        "Kataklarni tekshiring",
        "Dars sanalari/statuslarni ko‘ring; keng jadvalni yon tomonga surish mumkin. Kim o‘zgartirganini ko‘rish uchun Audit tarixi mavzusiga o‘ting.",
      ],
    ),
    tips: [
      "Import qilingan eski yozuvlar uchun taxminiy audit yaratilmaydi. Bo‘sh katak belgilanmaganini bildiradi, absent deb talqin qilinmaydi.",
    ],
  },
  {
    id: "admin-audit",
    title: "Davomat auditi: kim va nima sababli o‘zgartirgan",
    section: "Davomat",
    permission: P.ATTENDANCE_READ,
    destination: "attendance",
    summary:
      "Ko‘rish ruxsati bilan ham o‘zgarishlar muallifi va eski/yangi qiymatni tekshiring.",
    image: images.audit,
    imageAlt:
      "Audit ekranida guruh, dars sanasi va muallif/sabab/old-new jadvali raqamlangan.",
    steps: steps(
      [
        "Audit guruhini tanlang",
        "Davomat → Audit tarixi. Tekshiriladigan guruhni tanlang; yozish ruxsati talab qilinmaydi.",
      ],
      [
        "Dars sanasi",
        "Kerakli dars sanasini kiriting. Guruh yoki sana almashsa oldingi natija yopilib, yangi tarix alohida ochiladi.",
      ],
      [
        "Tarixni oching",
        "O‘zgarishlar tarixi tugmasini bosing. Bajaruvchi/rol, Toshkent vaqti, amal, eski va yangi status/izoh hamda sababni ko‘ring.",
      ],
    ),
    tips: [
      "Auditni tahrirlash/o‘chirish amali yo‘q. Eski importda audit mavjud bo‘lmasa taxminiy muallif yozilmaydi.",
    ],
  },
  {
    id: "admin-attendance",
    title: "Davomat qoralamasi va yakunlash",
    section: "Davomat",
    permission: P.ATTENDANCE_WRITE,
    destination: "attendance",
    summary: "Kerakli guruh va sanani tanlab har bir o‘quvchini belgilang.",
    image: images.attendance,
    imageAlt:
      "Admin davomat ekranida guruh/sana, o‘quvchi statuslari, qoralama va yakunlash belgilangan.",
    steps: steps(
      [
        "Guruh va dars sanasi",
        "Davomat olish bo‘limida guruh va sanani tanlang. Kelajak sanasiga davomat yozilmaydi.",
      ],
      [
        "Status va izoh",
        "Har bir faol o‘quvchini Keldi, Kelmadi yoki Kechikdi deb belgilang; zarur bo‘lsa izoh yozing. Hammani keldi qulayligini natijani tekshirgandan keyin ishlating.",
      ],
      [
        "Qoralamani saqlang",
        "Qoralama saqlash statuslarni saqlaydi, ammo darsni yakunlamaydi va notification yubormaydi.",
      ],
      [
        "Tekshirib yakunlang",
        "Barcha o‘quvchilar belgilanganini tekshirib Yakunlashni tasdiqlang. Davomat va Telegram notification navbati atomik saqlanadi.",
      ],
    ),
    tips: [
      "Bot/internetdagi yetkazish xatosi saqlangan davomatni yo‘qotmaydi. Takroriy yakunlash ikkinchi batch yaratmaydi.",
    ],
  },
  {
    id: "admin-correction",
    title: "Eski davomatni sabab bilan tuzatish",
    section: "Davomat",
    permission: P.ATTENDANCE_WRITE,
    destination: "attendance",
    summary: "O‘tgan kun yoki oy yozuvini tahrirlang, audit sababini yozing.",
    image: images.correction,
    imageAlt:
      "Yakunlangan admin davomatida status, tuzatish sababi va tuzatishni saqlash belgilangan.",
    steps: steps(
      [
        "Eski sanani oching",
        "Kerakli guruhning o‘tgan dars sanasini oching. Administrator uchun teacherning ikki kunlik cheklovi yo‘q.",
      ],
      [
        "To‘g‘ri statusni qo‘ying",
        "Xato status/izohni to‘g‘rilang. Belgilanmagan katakni taxmin bilan to‘ldirmang; manbani tekshiring.",
      ],
      [
        "Sababni yozib saqlang",
        "Mavjud davomatni tuzatish uchun sabab majburiy. O‘zgarishlar tarixida muallif, vaqt, sabab va old/new saqlanadi.",
      ],
    ),
    tips: [
      "Teacher ham ayni guruhga yozishi mumkin; parallel saqlash va qayta urinish auditni dublikat qilmaydi. Yakunlangan dars tuzatishda yakunlangan holatda qoladi.",
    ],
  },
  {
    id: "admin-messages",
    title: "Tanlanganlarga, guruhga yoki barchaga xabar",
    section: "Telegram",
    permission: P.MESSAGES_SEND,
    destination: "messages",
    summary:
      "Ota-ona/o‘quvchilarga matn tayyorlang va yuborish auditoriyasini tekshiring.",
    image: images.messages,
    imageAlt:
      "Xabarlar ekranida auditoriya turi, sarlavha, matn va yuborish tasdig‘i raqamlangan.",
    steps: steps(
      [
        "Auditoriyani tanlang",
        "Ota-onalar, O‘quvchilar yoki ikkalasi; keyin Tanlanganlar, Guruhlar bo‘yicha yoki Barchaga. Tanlanganlarda ism/farzand/guruh qidiruvi, sahifalar va ulanish filtri bor.",
      ],
      [
        "Sarlavha",
        "Qisqa sarlavha yozing yoki tahrirlanuvchi tayyor namunadan boshlang.",
      ],
      [
        "Matn va ko‘rib chiqish",
        "Matnni yozib Qabul qiluvchilarni ko‘rib chiqish bosing. Markaz nomi va sarlavha bilan jami 4096 limit; ulanmagan va takroriy chat soni ko‘rsatiladi.",
      ],
      [
        "Yuborishni tasdiqlang",
        "Yuborishni tasdiqlashni ochib matn/sonni yana tekshiring, Navbatga qo‘shishni bosing. Ro‘yxat yoki matn o‘zgarsa qayta preview kerak.",
      ],
    ),
    tips: [
      "Faqat botga ulangan faol hisoblar oladi; bir Telegram chatiga bir xabar. Unlinked hisobga xabar yuborilmaydi.",
      "Tarmoq xatosida ayni tasdiqni qayta urinib ko‘ring — request ID dublikat kampaniyani oldini oladi.",
    ],
  },
  {
    id: "admin-delivery",
    title: "Xabar tarixi, xatoli retry va to‘xtatish",
    section: "Telegram",
    permission: P.MESSAGES_SEND,
    destination: "messages",
    summary: "Har bir qabul qiluvchi holatini kuzating va navbatni boshqaring.",
    image: images.delivery,
    imageAlt:
      "Xabar tafsilotlarida holatlar, xatoli qayta urinish va navbatni to‘xtatish belgilangan.",
    steps: steps(
      [
        "Tarixni oching",
        "Yuborishlar tarixi orqali sarlavha yoki yuboruvchini qidiring va kerakli xabar tafsilotlarini oching.",
      ],
      [
        "Xatoli yuborishlar",
        "Xatoli yuborishlarni qayta urinish faqat failed holatdagilarni navbatga qaytaradi; tasdiq talab qiladi.",
      ],
      [
        "Navbatni to‘xtating",
        "Faqat qolgan pending xabarlar bekor qilinadi. Yetkazilgan xabarlar qayta yuborilmaydi va Telegramdan o‘chirilmaydi.",
      ],
    ),
    tips: [
      "Yetkazildi — Telegram qabul qildi; o‘qildi degani emas. Navbat vaqt, urinishlar va xato sabablarini saqlaydi.",
      "429da tizim belgilangan muddat kutadi, vaqtinchalik xatoda qayta urinadi. Worker qayta ishlaganda qolgan navbat davom etadi.",
    ],
  },
  {
    id: "admin-bot",
    title: "Botni sozlash, almashtirish va ulanishlar",
    section: "Telegram",
    superadminOnly: true,
    destination: "bot-settings",
    summary:
      "Production botini tekshirib ulang va worker tayyorligini kuzating.",
    image: images.bot,
    imageAlt:
      "Superadmin bot ekranida amaldagi holat, yangi token va tekshirilgan username belgilangan; token yopiq.",
    steps: steps(
      [
        "Amaldagi holat",
        "Bot sozlamalarida bot nomi va tayyor/sinxronlash holatini ko‘ring. Tayyor holat polling muvaffaqiyatli ekanini bildiradi.",
      ],
      [
        "Yangi tokenni saqlang",
        "BotFather bergan tokenni yopiq maydonga kiriting, yangilashni tasdiqlang. Server getMe orqali haqiqiy botni tekshiradi; noto‘g‘ri token eski konfiguratsiyani buzmaydi.",
      ],
      [
        "Username va ulanishlar",
        "Username amaldagi token botiga mos bo‘lishi kerak. Saqlangach barcha staff/parent/student havolalari yangilanadi. Boshqa botga o‘tilsa foydalanuvchilar yangi linkda Start bosishi kerak.",
      ],
    ),
    tips: [
      "O‘sha botning nom/token rotatsiyasi ulanishlarni saqlaydi. Boshqa botda eski parol, Telegram ID va davomat tarixi o‘chmaydi, ammo qayta Startgacha OTP/yetkazish kutadi.",
      "Tokenni screenshot, chat yoki public faylga chiqarmang. Full-admin permission bu bo‘limni ochmaydi.",
    ],
  },
];
