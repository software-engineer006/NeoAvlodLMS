# Audit operatsiyalari

Log ko‘rish va kunlik `.jsonl.gz` yuklash faqat faol superadminga berilgan.
Administrator uchun bunday permission mavjud emas. Panel va API logni
 o‘zgartirish/o‘chirish amallarini taqdim etmaydi. Qo‘llanma React namuna
ekranlari va raqamli qadamlar orqali Logs bo‘limini tushuntiradi.

Production deploy mavjud `.env.production` credentiallarini saqlaydi va faqat
yetishmagan audit kaliti, app/archiver URLlarini qo‘shadi. Migration owner
credentiali faqat deploymentga tegishli. API/Telegram worker `neoavlod_app`,
arxivchi `neoavlod_archiver` bilan ishlaydi; ular superuser emas. API uchun
`/app/audit-logs` read-only, arxivchi uchun private persistent katalog RW.
Shifrlangan yakuniy fayllar0400, katalog0700; Git/webroot ichida emas.

Arxivchi128tagacha eventni gzip va authenticated Fernet bilan yozadi, fsync,
read-back va hash/manifest tekshiradi, so‘ng metadata+exact-ID prune atomik
commit qiladi. Qisman yozilish, disk to‘lishi yoki buzilgan faylda eventlar
bazada qoladi; mavjud yakuniy fayl o‘chirilmaydi/ustiga yozilmaydi. Restartda
tekshirilgan orphan qayta ishlatiladi. FIFO/symlink va traversal rad etiladi.
Har15soniya heartbeat yangilanadi;45soniyadan eski heartbeat unhealthy.

Har deploy oldidan private PostgreSQL dump va yonida `.audit.tar.gz` yaratiladi.
Tar persistent encrypted fayllar va kalit/credential envini saqlaydi; ushbu
backupni ham maxfiy va alohida saqlash kerak. Kalit yo‘qolsa shifrlangan
arxivni qayta ochib bo‘lmaydi. Retention/purge/delete avtomatik yo‘q.

Normal rollback faqat audit-compatible `backend/audit_runtime.version=1`
releasega ruxsat beradi; DB schema, navbat, metadata, kalit va arxivga tegmaydi.
Auditdan oldingi runtimega qaytish rad etiladi va app writers to‘xtatiladi:
auditni chetlab o‘tuvchi owner-credential backendni ishga tushirish mumkin emas.
Bunday vaziyatda tekshirilgan audit-compatible release bilan deployni takrorlang.
Birinchi audit deploy muvaffaqiyatsiz bo‘lsa maintenance holati saqlanadi.

Business-data restore qilishdan oldin writers/arxivchini to‘xtating va yangi
full backup+key/archive backup oling. Alohida scratch DBga dumpni restore
qilib, biznes qatorlarini tekshiring. Productionga business schema/data uchun
reviewed selective restore qo‘llang; `audit` schema, event/segmentlar va
`attendance_changes` dalillarini DROP/TRUNCATE/replace qilmang. Audit
migrationlarini downgrade qilmang. Reconciliation audit source bilan yoziladi;
canonical eski/new davomat delta uchun sabab saqlanishi shart. To‘liq eski
DB snapshotni production ustiga restore qilish auditni yo‘qotadi va qo‘llab
quvvatlanmaydi. Falokat recoveryda eng yangi DB+metadata va barcha encrypted
fayllarni shu backupning kalitlari bilan scratchda birga tekshiring.

Kalit almashtirishda yangi unique `NEOAVLOD_AUDIT_KEY_ID` va yangi kalit kiriting;
eski ID/kalitlarni `NEOAVLOD_AUDIT_PREVIOUS_KEYS` JSONda saqlang (max8). API va
arxivchini birga restart qiling; eski/yangi segment read-backni tekshiring.
Eski arxiv mavjud ekan uning kalitini olib tashlamang. Env/kalitni chatga,
Gitga, CI outputga yoki qo‘llanma ekraniga chiqarmang.

DB owner/root operator infratuzilmani boshqaradi; app superadmin bu huquqqa ega
emas. Dastur/DB grants/read-only mount app orqali o‘chirishni rad etadi;
hardware WORM yoki root administratorga qarshi kafolat berilmaydi. Buning
uchun tashqi immutable backup storage kerak. Ishonchli eski loglar mavjud
bo‘lmagan davrga yangi xodim/time attribution uydirilmaydi.

2026-10-14 production qabuli:0012 head, runtime
b1a39b64cc8cedcaff9f309792438a007d4c5b44; CI/CD38547243448 successful.
Restricted role, read-only API mount, encrypted read-back, archiver restart va
stable key tekshirildi. Pre-audit va post-audit DB+encrypted-files/key private
backuplari tekshirildi. Hozirgi audit-compatible release birinchi audit release;
oldingi8db08f7 runtime auditdan oldingi bo‘lgani uchun rollback uchun yaroqsiz.

2026-10-14 yangi UI/runtime:ffc4fb0e51fbe93171ed375316593290e76dcbf6,
CI/CD38555952928 successful. Sana14.10.2026, vaqt HH:mm:ss Toshkent;
HTTP logda verified session portal va bo‘lim/amal tavsifi, raw route/method
texnik dalil sifatida qoladi. API o‘qish so‘rovi page-click deb uydirilmaydi.
Production actual HTTPS davomat sinovi alohida AUDIT SINOV116 guruh/o‘quvchi
va qisqa robot sessiyalarida bajarildi, OTP login testi emas. Uch test xodimi,
guruh va o‘quvchi inactive, sessiyalar revoked; canonical attendance/batch va
immutable dalillar FK sabab o‘chirilmaydi. Haqiqiy mijoz qatorlari o‘zgarmadi.
18active admin/teacher403 check va new portal attribution tasdiqlandi;
shifrlangan correction dalillari yangi deploydan keyin ham aynan saqlandi.
