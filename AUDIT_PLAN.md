# Audit va React qo‘llanma — 2026-10-14 reja

## Natija

Xodimning autentifikatsiyalangan amali, muvaffaqiyatsiz urinishlari va biznes
o‘zgarishlari tekshiriladigan auditga yoziladi. Xodimning ID/ism/login/rol
snapshoti, UTC vaqt (mikrosoniya bilan), Toshkent kuni, amal, obyekt, natija,
eski/yangi qiymatlar, sabab va request correlation ID saqlanadi. UI vaqtni
Asia/Tashkent bo‘yicha soniyagacha ko‘rsatadi; eksport UTC va mahalliy kunni
aniq beradi. Oldingi harakatlar haqida uydirma audit yaratilmaydi; mavjud
AttendanceChange yozuvlari asl actor/time/reason bilan saqlanadi.

Log ko‘rish/yuklash faqat faol superadminning admin sessiyasi uchun. Bu yangi
administrator permissioni emas. Administrator, barcha grantli administrator,
teacher va anonim foydalanuvchi API hamda UI orqali auditga kira olmaydi.
Mavjud davomat o‘zgarishlari auditi ham shu rol chegarasiga o‘tadi; odatiy
davomat tarixi/statistikasi o‘z amaldagi ruxsatlarida qoladi.

## Arxitektura va xavfsizlik chegarasi

Mavjud ulanish nuqtalari: `api/deps.py:current_identity` barcha protected
route actorini tasdiqlaydi; `Database/get_session` async tranzaksiyani beradi.
`services/staff,subjects,groups,students,attendance,bot_settings,messages` CRUD
va domain commitlarini boshqaradi. `api/auth`, `security/sessions` va
`services/login,passwords,onboarding,bot_worker` auth/Telegram provenance
uchun tekshiriladi. `models/attendance.py:AttendanceChange` mavjud old/new/reason
manbai; `admin_attendance.changes` va `teacher.get_attendance_changes` hozir
non-superadminlarga ham ochiq,109da yopiladi. `guide/GuideView/types/*Topics`
PNGga bog‘liq;111da scene registryga o‘tadi. `compose.prod.yaml`,
`scripts/deploy/{deploy,backup,common,rollback}.sh` volume/key/role va auditni
saqlaydigan rollback nuqtalari; mavjud rollback odatda DBni ortga tiklamaydi,
qo‘lda business restore esa audit schemani istisno qilishi kerak.

1. `audit` PostgreSQL schema: append-only qisqa muddatli navbat va arxivning
   ixcham metadatasi. Biznes FKlariga bog‘liq bo‘lmagan actor/entity snapshotlar
   hisob keyinchalik o‘zgarsa ham audit ma’nosini saqlaydi.
2. Muhim biznes jadvallari uchun parametrsiz, whitelistli DB triggerlar:
   staff/permission/profile, subject, group/schedule/status, student/parent va
   student-group bog‘lanishi, davomat o‘zgarishi/yakunlash, bot konfiguratsiyasi,
   xabar kampaniyasi boshqaruvi. Audit yozilmasa biznes tranzaksiyasi rollback
   bo‘ladi. Tranzaksiya no-op bo‘lsa uydirma mutation yozilmaydi.
3. Server tasdiqlagan actor/request konteksti SQLAlchemy sessiyasiga bog‘lanadi;
   yangi tranzaksiyada qayta o‘rnatiladi. Login/OTP/reset/logout/Telegram va
   worker amallari alohida provenance oladi. HTTP o‘qish/403/422/5xx urinishlari
   ham body, cookie, token va raw URL/querysiz yoziladi. API o‘qishlaridagi
   pagination/polling yozuvlari ixcham bo‘ladi.
4. Attendance status/izohi mavjud yozuvda o‘zgarsa teacher/admin/superadmin
   sabab kiritadi. Eski/yangi holat, sabab, actor va vaqt o‘sha tranzaksiyada
   auditga tushadi. Yangi belgilash va o‘zgarishsiz yakunlash sabab talab qilmaydi.
5. Runtime DB roli auditni UPDATE/DELETE/TRUNCATE qila olmaydi; arxivchi uchun
   alohida credential va cheklangan DB roli ishlatiladi. Nazoratli archive/prune
   funksiyasi faqat tekshirilgan arxivga mos aniq eventlar uchun ishlaydi.
   Superadminning HTTP huquqi infratuzilma yoki SQL owner huquqini bermaydi.
6. Alohida archiver: bounded batch, PostgreSQL singleton lock, deterministik
   gzip JSONL va autentifikatsiyalangan shifrlash. Barqaror alohida arxiv kaliti
   private konfiguratsiyada; versiya/key ID key rotation uchun saqlanadi.
   `audit-logs` persistent papkasi web rootdan tashqarida. API mounti read-only;
   archiver O_EXCL/O_NOFOLLOW, regular-file tekshiruvi, fsync va private modes
   bilan yangi segment yaratadi. Mavjud segment qayta yozilmaydi/o‘chirilmaydi.
7. Fayl qayta ochilib checksum/decrypt/count/event IDs tekshirilgach metadata
   atomik commit bo‘ladi; faqat shundan keyin navbat payloadi tozalanadi. Crash,
   disk-full, ikki archiver, retry, orphan va duplicate holatlari ma’lumotni
   yo‘qotmasdan tiklanadi. Arxivlarni avtomatik o‘chirish/retention bo‘lmaydi.
8. Kunlik ko‘rish/export persisted segmentlar va hali arxivlanmagan navbatni
   bir xil snapshot/cursor bilan birlashtiradi. Bitta kun uchun `.jsonl.gz`,
   bounded-memory o‘qish, integrity tekshiruvi, safe filename, no-store va
   attachment headers. Path/symlink/traversal yoki boshqa kun/rolni chetlab
   o‘tish mumkin emas. Download ham auditga tushadi.
9. Parol/hash, OTP, access/refresh, cookie/CSRF, bot tokeni, encryption key,
   credential payload va onboarding capability havolalari logga yozilmaydi.
   Diff faqat kerakli maydonlarda; max payload/batch, bounded streaming va
   siqilish o‘lchovi bilan xotira/disk xarajati tekshiriladi.
10. Ilovadagi superadmin logni o‘zgartira/o‘chira olmaydi. Host root va DB owner
    infratuzilma ishonch chegarasidir; kod ular ustidan mutlaq WORM kafolatini
    da’vo qilmaydi. Audit schema/folder/key backup va rollbackda saqlanadi;
    business DB restore audit dalillarini ortga qaytarmasligi kerak.

## Frontend va qo‘llanma

- Admin dashboarddan Xush kelibsiz olib tashlanadi; faqat asosiy ko‘rsatkichlar.
- Ikki portal Tailwindning tekshirilgan eng yangi stable versiyasiga Dockerda
  o‘tadi; npm lockfile aniq versiyalarni mahkamlaydi. CSS-first konfiguratsiya,
  portal/shared source detection, mavjud dizayn va mobil oqimlar tekshiriladi.
  Rasmiy [upgrade guide](https://tailwindcss.com/docs/upgrade-guide) va
  [browser compatibility](https://tailwindcss.com/docs/compatibility) asos bo‘ladi.
- Foydalanuvchi aniqlashtirishi: qo‘llanma qayta ishlatiladigan React componentlar
  va optimal latest Tailwind bilan quriladi; HTML/CSS misol sifatida aytilgan.
- PNG screenshotlar o‘rniga haqiqiy shared UI atomlaridan qurilgan deklarativ
  React/HTML/CSS namuna ekranlari. Sintetik ism/sonlar, raqamli qadam markerlari,
  responsive konteyner va tiniq zoom. Demo API chaqirmaydi, haqiqiy mutation,
  submit, credential yoki Telegram havolasi yo‘q; klaviatura bilan boshqaruv
  qo‘llanmaning o‘z qidiruv/zoom/navigatsiya elementlarida qoladi.
- Scene registry va renderer portalga bo‘linadi; teacher bundlega superadmin
  audit/bot/grant qo‘llanmasi kirmaydi. Barcha mavjud kerakli mavzu/qadamlar
  saqlanadi, auditga oid teacher/admin ko‘rsatmalar yangi rolga moslanadi.
- Superadmin Logs bo‘limi: kunlar/sonlar, vaqt/xodim/amal/obyekt/natija/sabab,
  filtr va pagination, detail old/new, kunlik download. Delete/edit UI/API yo‘q.
  Superadmin qo‘llanmasiga tanlash, tekshirish, yuklash va format mavzusi qo‘shiladi.

## Dizayn va tekshiruv

Capture, archive repository/cipher, query va API ajratiladi. Whitelist action
registry DB Observer triggerlarini hosil qiladi; serializer/format/RBAC yagona
joyda qoladi. SOLID/DRY/KISS konkret takror va mas’uliyatlarga tatbiq qilinadi;
keraksiz universal framework yoki parallel implementatsiya kiritilmaydi.

TEST_PLAN.md ga atomik rollback, actor spoof, no-op/concurrency, time boundary,
role/CSRF/session, SQL immutable guards, archive crash/corruption/path/disk-full,
download snapshot, memory/compression, DOM guide va 1440/768/360 UI holatlari
qo‘shiladi. Real oilalarga test xabari yuborilmaydi. Docker full checks, migration,
production release/backup/rollback integratsiyasi, public diff/secret scan,
non-force GitHub push, actual green CI/CD va HTTPS/data/worker/log readiness
dalilidan keyin registry yakunlanadi. Vazifalar TASKS.md da ketma-ket.
