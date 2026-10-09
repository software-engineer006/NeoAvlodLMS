# NeoAvlodLMS — vazifalar va davom ettirish holati

## Ish doirasi va joriy holat

Talablar manbasi: foydalanuvchining 2026-10-05 dagi topshiriqlari. Joriy doira:
Docker muhitini hozir yaratish va qolgan barcha vazifalarni ketma-ket Docker
muhitida bajarish. Kod tahriri hostda mumkin; backend, bot, frontend, test,
lint, typecheck, migratsiya va task-manager Python jarayonlari konteynerda.
Host Python/Node/venv ishlatilmaydi. Oldingi Task 001 hostda tekshirilgan;
Task 002 dan barcha tekshiruvlar Dockerda qayta bajariladi.

2026-10-08 qo‘shimcha talablar: xodimga avtomatik parol va Telegram orqali
login ma’lumotlarini berish; «O‘quvchilar» nomlanishi va batafsil profil modali;
professional admin UI, yig‘iladigan sidebar va Dashboard statistikasi; barcha
xodimlar uchun profil, parol va rasm boshqaruvi; login sahifasida NeoAvlod logosi;
teacher uchun qulay davomat; guruh/oy bo‘yicha davomat tarixi va o‘quvchining
oylik statistikasi. Ushbu talablar 046–060 vazifalarda amalga oshirildi;
umumiy live acceptance 071 da saqlangan. Haqiqiy CSV va hisoblar talabi
061–070 vazifalarda ketma-ket bajarilmoqda.

Bu fayl loyiha holatining asosiy manbasi. Belgilar: `[ ]` kutilmoqda,
`[/]` bajarilmoqda, `[x]` tekshiruvdan o‘tgan. Bir vaqtda faqat bitta vazifa
faol bo‘ladi. Vazifalar ketma-ket bajariladi; har biri alohida tekshiriladigan
natijaga ega. Oldingi vazifalarga bog‘liqliklar qabul mezonlarini almashtirmaydi.

Davom ettirish: `scripts/agent_skills/task.sh resume` mavjud faol
vazifani qaytaradi yoki birinchi bajarilmagan vazifani boshlaydi. Yakunlash:
`scripts/agent_skills/task.sh done 001 --evidence 'tekshiruv natijasi'`.
Tekshiruv muvaffaqiyatsiz bo‘lsa vazifa `[/]` holatda qoladi.

Tayyorlov holati: rejalashtirish va agent skriptlari bajarildi. 2026-10-05:
`check_agent_skills.sh` — 12 regressiya testi, shell sintaksisi va dastlabki 40 task
invariantlari tekshiruvdan o‘tdi.

## Arxitektura qarorlari

- Monorepo: `backend/src/neoavlod/`, `backend/tests/`, `backend/alembic/`,
  `frontend/apps/admin/`, `frontend/apps/teacher/`, `frontend/packages/ui/`,
  `infra/`, `.github/workflows/`, `scripts/agent_skills/`.
- Python 3.12+; FastAPI, Pydantic v2, SQLAlchemy 2 async, asyncpg va Alembic.
  PostgreSQL yagona doimiy ma’lumotlar ombori. API `/api/v1` prefiksida;
  boshqaruv routerlari `/api/v1/admin`, teacher routerlari `/api/v1/teacher`.
  API, Telegram worker va PostgreSQL alohida Docker xizmatlarida ishlaydi.
- React/TypeScript/Tailwind/lucide-react, Inter va o‘zbekcha UI. Admin va teacher
  alohida Vite ilovalari; umumiy UI/API mijoz npm workspace orqali ulashiladi.
  Emoji ishlatilmaydi. Har bir ilova o‘z subdomenida `/api` orqali ishlaydi.
- Har bir himoyalangan so‘rovda faol xodim, portal va permission tekshiriladi.
  Superadmin barcha huquqlarga ega, admin faqat tanilgan permission kalitlari
  bilan ishlaydi. Teacher admin portaliga backend va frontendda 403 oladi;
  guruh va talaba uchun ownership SQL so‘rovi bilan tekshiriladi.
- Permission katalogi: `staff:manage`, `subjects:manage`, `groups:read`,
  `groups:create`, `groups:edit`, `students:read`, `students:create`,
  `students:edit`, `attendance:read`. Bot sozlamalari faqat superadmin uchun.
  Davomatni yozish faqat biriktirilgan teacher uchun, superadmin uchun ham emas.
- Xodimlarda qo‘shimcha `auth_uuid` mavjud: `staff_<uuid>` bot havolasi orqali
  Telegram ulanadi. Parent/student havolalari mos ravishda `parent_<uuid>` va
  `student_<uuid>`. UUID taxmin qilib bo‘lmaydi; bog‘lash bir martalik,
  tranzaksion va mavjud boshqa Telegram hisobiga qayta bog‘lashni rad etadi.
- Parollar Argon2 bilan hash qilinadi. Username/parol tekshirilgach Telegramga
  6 raqamli, qisqa muddatli OTP yuboriladi. OTP maqsadi, urinishlar limiti,
  muddati va bir martalik ishlatilishi DB orqali tekshiriladi; kod loglanmaydi.
- Qisqa access session va rotatsiyalanuvchi refresh token: refresh oilasi uchun
  mutlaq 7 kunlik muddat, qayta ishlatish aniqlansa oilani bekor qilish.
  HttpOnly, Secure, host-only cookie; SameSite va CSRF/Origin tekshiruvi.
  Teacher/admin loginlarining portal chegarasi serverda tekshiriladi;
  session portalga bog‘lanadi va serverda token hash saqlanadi.
- Eski parol bilan o‘zgartirishda OTP talab qilinmaydi. Parolni unutishda
  autentifikatsiyasiz Telegram OTP kerak; username mavjudligi oshkor qilinmaydi.
  Parol o‘zgarganda/reset bo‘lganda mavjud sessionlar bekor qilinadi.
- Guruhga talaba qo‘shish/ko‘chirishda guruh satri `FOR UPDATE` bilan qulflanadi;
  faol talabalar soni `max_students` dan oshmaydi. Ko‘chirishda ikki guruh
  deterministik tartibda qulflanadi. Narx Decimal, valyuta UZS; kunlar 1–7,
  dars vaqtlari Asia/Tashkent mahalliy vaqti, audit va token vaqtlari UTC.
- Student va parent bir tranzaksiyada yaratiladi. Parent takroriy telefon uchun
  avtomatik birlashtirilmaydi. Yosh, telefon, jadval va FK lar validatsiya qilinadi.
- Davomat uchun `(group_id, student_id, date)` unique. Draftlarni faqat guruh
  teacheri yozadi. Yakunlash guruh/sana uchun bir marta va atomik bajariladi;
  faol talabalarning barchasi belgilanadi. Yakunlangan davomat keyin o‘zgarmaydi.
- Davomat yakunlanganda notification outbox shu DB tranzaksiyasida yoziladi.
  FastAPI Background Task tezkor dispatchni boshlaydi; alohida worker retry va
  restartdan tiklanishni ta’minlaydi. Telegram tarmog‘i uzilishi davomatni yo‘qotmaydi.
  Yetkazish at-least-once; tashqi Telegram sendMessage timeoutida dublikat xavfi bor.
- Bot tokeni DB da shifrlanadi; kalit server secretidir. API javoblari va loglarda
  token qaytarilmaydi. Tokenni tekshirish, bot username va versiyani saqlash,
  workerning eski pollingni to‘xtatib yangi konfiguratsiyani yuklashi talab qilinadi.
  Webhook/polling birga ishlamaydi; bitta polling worker faol bo‘ladi.
- Birinchi login uchun bootstrap ketma-ketligi: migratsiya → superadmin CLI →
  boshlang‘ich bot tokenini yashirin kirituvchi settings CLI → bot worker →
  superadminning staff havolasini bosishi → web login/OTP. Keyingi token
  o‘zgarishlari superadmin UI orqali; OTPni chetlab o‘tuvchi login mavjud emas.
- Nginx ikki frontendni statik tarqatadi va APIga proxy qiladi. GitHub Actions
  frontendlarni build qilib `/var/www/NeoAvlod/admin-frontend` va
  `/var/www/NeoAvlod/teacher-frontend` ga yetkazadi. TLS, migrations, health,
  backup/restore va rollback deployment qo‘llanmasida ko‘rsatiladi.

## Docker muhitida majburiy ish tartibi

- Barcha agentlar avval [AGENTS.md](AGENTS.md), [resume skilli](skills/neoavlod-resume/SKILL.md)
  va shu reestrni o‘qiydi. Faol `[/]` task bo‘lsa aynan shundan davom etiladi.
- `scripts/agent_skills/docker_env.sh up`: local secret yaratish, image build,
  database/backend/test-database healthni kutish. PostgreSQL `18.6`, 2026-10-05
  da [rasmiy eng yangi stable](https://hub.docker.com/_/postgres); volume
  `/var/lib/postgresql` ga mount qilinadi. Major version avtomatik o‘zgarmaydi.
- `scripts/agent_skills/task.sh resume`, `check_backend.sh`, `check_frontend.sh`,
  `run_migrations.sh`, `check_agent_skills.sh` hostdan chaqirilganda Dockerga kiradi.
  Docker ishlamasa xato qaytadi; host tekshiruviga fallback yo‘q.
- DB testlari faqat `test-database` xizmatida. Development DB volume o‘chirilmaydi.
  `docker compose down -v`, mavjud data volume yoki image major upgrade kabi
  ma’lumotni yo‘qotadigan amallar alohida ruxsatsiz bajarilmaydi.
- Har bir task: resume → kod → Docker tekshiruv → dalil bilan done → keyingi task.
  Bir task mezonlari tugamaguncha keyingi taskga o‘tilmaydi. Sessiya uzilganda
  bajarilmagan natija yakunlandi deb belgilanmaydi.
- Runtime dependencysi o‘zgarsa `docker_env.sh build`, so‘ng backend restart.
  Kod bind mount orqali yangilanadi; frontend Node ishlari Node konteynerida.

## Davom ettirish checkpoint

Faol registry task: Yo‘q; 001–082 yakunlangan. Public GitHub main uchun 169 faylli release 92b636bf871dbe84eff1ff7059074e11745965c0 non-force push bilan tasdiqlandi. Actual secret/password/student-name scan findings=0, unrelated output/ va private data chiqarildi. Docker 225 backend test, yangilangan frontend build/checksum, 13 agent testi, legacy synthetic fixture va real production import/rollback/cleanup exit 0. Eski GitHub Actions root-owned cleanup xatosi tuzatildi. Release Actions 37908343083 in_progress; yakuniy CI/deploy natijasi hali tasdiqlanmagan. Local CEO Mohira va Dilmurod allaqachon Telegramga ulangan; Jasurbekning amaldagi bir martalik havolasi .private/python-groups/TELEGRAM_LINKS.jsonda (0600), IDs/parollar Gitda yo‘q. Keyingi qadam: push qilingan eng oxirgi SHA Actions holatini tekshirish va foydalanuvchiga natija/linklarni berish. Production private paket hali serverga yuborilmagan; local havolalar hozirgi neoavlod_demo bazasiga tegishli. 076–080 local data dalillari saqlangan.
2026-10-09 educenter_data/ CSV haqiqiy davomat integratsiyasi (072–075) yakunlandi:
- 10 ta guruh bo‘yicha 29 ta dars sanasi (YYYY-MM-DD) xaritalandi.
- neoavlod_demo bazasiga 29 ta AttendanceBatch va 302 ta Attendance yozuvi (162 present, 140 absent, 28 izoh) qo‘llandi.
- Qayta ishga tushirishda idempotentlik (0 yangi yozuv) va atomik rollback tasdiqlandi.
- Admin (port 3000) va Teacher (port 3001) portallarida oylik davomat tarixi va o‘quvchilar profillaridagi oylik davomat statistikasi haqiqiy ma’lumotlar bilan to‘liq ishlayapti.
- Docker check_backend (219 pytest, Ruff, mypy 101 fayl), check_frontend (typecheck, lint), run_migrations va check_agent_skills (13 test) to‘liq o‘tdi.
Quyidagi eski checkpoint qaydlari tarixiy; joriy holat yuqorida. Eski demo
hisoblari 066 da backupdan keyin tozalanadi; local ekranda OTP ko‘rsatilmaydi.
Task 045: Redis OTP (TTL 300s, max 5 urinish, atomik Lua script), `otp_challenges` jadvalini o‘chirish (0003 migratsiyasi), local demo OTP endpointi va UI ko‘rinishini olib tashlash, bot username sozlamasi va ulanmagan xodim uchun "Telegram botga hali ulanmagan" xabari to‘liq amalga oshirildi. Dockerda check_backend (168 test, Ruff, mypy), check_frontend (typecheck, lint, 93 vitest test), run_migrations, check_agent_skills (13 test, 61 task/45 bajarilgan) va local_demo up/smoke muvaffaqiyatli o‘tdi.
Navbatdagi faol vazifa: 046 — Xodim yaratishda avtomatik vaqtinchalik parol API.
Task 044: explicit hash bucket 64, bootstrap/production uch domen ACME 200/404,
Nginx portal/proxy regressiyasi va 13 agent testi Dockerda o‘tdi; local demo tiklandi.
Serverda nginx.conf http sozlamasini 64 ga o‘zgartirish, nginx -t va muvaffaqiyatli
reload, uch public ACME URLdan keyin Certbot — navbatdagi live qadam.
Task 043: Ubuntu SSH clone va alohida CI kaliti, local committed frontend build,
exact main SHA deploy, versioned backend image, ikki portal, backup/migration,
avtomatik/qo‘lda rollback va Nginx 1.24 webroot TLS mosligi Dockerda tekshirildi.
169 backend / 85 frontend / 8 deploy / 13 agent test, lint/typecheck/build,
actionlint va real disposable production deploy/rollback muvaffaqiyatli.
Haqiqiy VPS/Actions/Telegram hali tasdiqlanmagan: server host identity,
CI SSH kaliti va GitHub production environment/secrets sozlanishi kerak.
Foydalanuvchi yuborgan qiymat VPS paroli ekanini tasdiqladi; secret saqlanmadi.
GitHubga local demo/CSRF va deployment/CI/CD alohida commitlar bilan yuborilgan;
frontend release checksumlari qayta tasdiqlandi, secretlar va local UI rasmlari chiqarildi.
Pushdan keyingi amaliy qadam: GitHub Actions test/deploy holatini tekshirish,
`DEPLOYMENT.md` bo‘yicha root@189.74.99.79 serverini sozlash va live acceptance.
Local demo manzillari:
admin `http://localhost:3000`, teacher `http://127.0.0.1:3001`, API `http://localhost:8000`.
Hisoblar va 3 talabalik demo guruh alohida `neoavlod_demo` bazasida; local OTP ekranda ko‘rinadi.
169 backend / 85 frontend / 13 agent test, lint/typecheck/build, live portal smoke va
brauzerda teacher davomat qoralamasini saqlash tekshirildi. CSRF cookie nomi moslashtirildi.
Qo‘llanma: `LOCAL_DEMO.md`; Docker socketi uchun sandbox escalation kerak bo‘lishi mumkin.

## Agent skriptlari bilan ishlash

- `scripts/agent_skills/check_agent_skills.sh`: task manager regressiya testlari,
  shell sintaksisi va reestrning invariantlarini tekshiradi.
- `scripts/agent_skills/check_backend.sh`: compileall, Ruff, mypy, pytest.
- `scripts/agent_skills/check_frontend.sh`: root frontend typecheck va lint;
  ilovalar yaratilmaguncha aniq xato bilan to‘xtaydi.
- `scripts/agent_skills/run_migrations.sh`: Alembic upgrade, head bilan moslik,
  model/migration diff tekshiruvi; DB yoki Alembic yo‘q bo‘lsa to‘xtaydi.
- Tekshiruvni o‘tkazib yuborish muvaffaqiyat hisoblanmaydi. Skriptlar loyiha
  rootini o‘z joylashuvidan topadi va chaqiruvchi katalogga bog‘liq emas.

## Backend arxitekturasi

- [x] 001 — Backend skeleti, konfiguratsiya va health endpoint.
  - Qabul: install qilinadigan pyproject, FastAPI app factory, `/api/v1/health`,
    Pydantic settings, `.env.example`, testlar; backend skripti to‘liq o‘tadi.
  - Dalil: 2026-10-05: check_backend.sh — compileall, Ruff, mypy (8 fayl), pytest (9 passed); check_agent_skills.sh — 12 test, shell sintaksisi va reestr invariantlari o‘tdi.
- [x] 002 — Docker development muhiti va agent resume skilli.
  - Qabul: postgres:18.6 rasmiy eng yangi barqaror image, persistent volume,
    alohida disposable test DB, nonroot backend Dockerfile, Compose healthy API,
    barcha check/migration/task skriptlari Dockerda; AGENTS.md va loyiha SKILL.md
    mavjud faol taskdan davom ettirishni belgilaydi; Docker smoke va testlar o‘tadi.
  - Dalil: Docker: PostgreSQL 18.6 + nonroot API healthy; smoke HTTP 200; backend Ruff/mypy/9 pytest; 13 agent tests; SKILL quick_validate passed.
- [x] 003 — Asinxron PostgreSQL session va model bazasi.
  - Qabul: SQLAlchemy 2 async engine/session dependency, naming convention,
    rollback/close lifecycle va DB readiness testi; secret DSN loglanmaydi.
  - Dalil: Docker PostgreSQL 18.6: compileall/Ruff/mypy passed; 16 pytest passed; explicit commit, rollback, uncommitted close, lifespan cleanup, masked errors; live health and readiness HTTP 200.
- [x] 004 — Staff va Subject modellari.
  - Qabul: UUID id, unique username/phone, role/status, JSONB permissions,
    Telegram id va staff auth_uuid; subject name/description/is_active; DB testlari.
  - Dalil: Docker PostgreSQL: Ruff/mypy/compileall passed; 30 pytest passed including UUID/defaults, mutable JSONB, unique phone/username/Telegram/auth UUID and DB check constraints.
- [x] 005 — Group, Parent va Student modellari.
  - Qabul: barcha talab qilingan maydonlar, FK/index/check constraintlar,
    Decimal price, jadval va UUID linklar; invalid ma’lumotlar DB da rad etiladi.
  - Dalil: Docker PostgreSQL: compileall/Ruff/mypy passed; 47 pytest passed including Decimal, schedule/day limits, capacity bounds, age, FK, parent/student UUID and parent phone duplication.
- [x] 006 — Attendance, settings, auth va outbox modellari.
  - Qabul: attendance unique, finalization, OTP/session/refresh revocation,
    shifrlangan bot sozlamasi va durable outbox constraintlari tekshiriladi.
  - Dalil: Docker PostgreSQL: compileall/Ruff/mypy passed, 52 pytest passed; attendance/finalization uniqueness, OTP hash/expiry/attempt bounds, session/refresh uniqueness, settings singleton/version and outbox idempotency/payload DB checks.
- [x] 007 — Boshlang‘ich Alembic migratsiyasi.
  - Qabul: bo‘sh PostgreSQLda upgrade va disposable DBda downgrade/upgrade,
    bitta head va `alembic check` o‘tadi; barcha modellarga mos schema.
  - Dalil: Docker PostgreSQL: 54 pytest, Ruff/mypy/compileall including migration files passed; disposable DB upgrade/downgrade/upgrade + schema/constraint comparison + offline SQL passed; development DB upgrade head/current check_heads/alembic check passed.
- [x] 008 — Password hashing va superadmin bootstrap CLI.
  - Qabul: Argon2 verify/rehash, kuchli parol validatsiyasi, secretni yashirin
    kiritish, idempotent bootstrap; default production paroli mavjud emas.
  - Dalil: Docker PostgreSQL: 63 pytest, Ruff/mypy/compileall passed; Argon2 random salt/verify/rehash; weak password rejection; idempotent and concurrent bootstrap; existing teacher cannot be promoted; stdin CLI secret not echoed.
- [x] 009 — Staff Telegram onboarding havolalari.
  - Qabul: xodim yaratishda bot username bilan staff havolasi, tokenni yangilash
    oqimi, ulanganlik holati; noma’lum/ishlatilgan linklar tekshiriladi.
  - Dalil: Docker: 72 pytest + compileall/Ruff/mypy passed; staff/parent/student links, expired/used/inactive validation, staff UUID rotation, connected account relink prevention; API validation errors never echo sensitive inputs.
- [x] 010 — Cookie session, refresh rotation, logout va CSRF.
  - Qabul: HttpOnly/Secure cookie, 7 kun mutlaq refresh muddati, replay revoke,
    logout, Origin/CSRF hamda yaroqsiz/expired/revoked token testlari o‘tadi.
  - Dalil: Docker PostgreSQL: 82 pytest + compileall/Ruff/mypy passed; hashed opaque tokens, HttpOnly/Secure/host-only cookies, absolute 7-day refresh, durable replay revoke, Origin/CSRF, logout even without refresh cookie, expired/inactive and teacher/admin 403.
- [x] 011 — Username/parol va Telegram OTP bilan login API.
  - Qabul: OTPgacha session berilmaydi; 6 raqam, TTL, urinish/rate limit,
    inactive staff va portal xatolari, Telegram ulanmagan holat tekshiriladi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 43 fayl, 95 test; 0002 migratsiya head/check; backend health/ready va PostgreSQL 18.6 smoke OK
- [x] 012 — Parolni o‘zgartirish va unutgan parolni tiklash API.
  - Qabul: eski parol bilan almashtirish OTPsiz; reset Telegram OTP orqali;
    kod bir marta ishlaydi, generic javoblar va session revoke testlari o‘tadi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 45 fayl, 98 pytest passed; old-password change without OTP (wrong old 401, weak 422, bad CSRF 403) revokes all sessions; reset 202 generic for known/unknown/unlinked/delivery-failure, purpose-bound one-time Telegram OTP, login OTP rejected, replay 401, sessions revoked
- [x] 013 — RBAC va portal permission dependencylari.
  - Qabul: superadmin/admin permission matritsasi, teacher admin uchun 403,
    ownership va inactive user testlari; noma’lum permission rad etiladi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 48 fayl, 106 pytest passed; permission katalogi 9 kalit, superadmin hamma, admin faqat saqlangan kalitlar, teacher hech qaysi; noma'lum permission 422/ValueError; teacher admin routelarda va admin/superadmin teacher routelarda 403; inactive 401, demote/permission o'zgarishi darhol 403; ownership SQL EXISTS bilan, begona/yo'q guruh va talaba 404; unsafe so'rovlarda Origin+CSRF
- [x] 014 — Staff boshqaruv API.
  - Qabul: pagination/search/create/edit/deactivate; admin yaratish va permission
    biriktirish faqat superadmin; oxirgi superadminni o‘chirish bloklanadi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 51 fayl, 113 pytest passed; /api/v1/admin/staff pagination/search/filter, create/edit/activate/deactivate, telegram-link; admin faqat teacher boshqaradi, admin yaratish va permission biriktirish faqat superadmin; noma'lum permission 422; duplicate 409; deactivate sessionlarni bekor qiladi; oxirgi faol superadmin va o'zini o'chirish bloklanadi; parol/hash/auth_uuid javobda yo'q
- [x] 015 — Subject CRUD API.
  - Qabul: subjects:manage, validatsiya, pagination, is_active, bog‘langan
    guruhlar uchun xavfsiz deactivate va ruxsatsiz so‘rov testlari.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 54 fayl, 117 pytest passed; /api/v1/admin/subjects subjects:manage, pagination, search, is_active, duplicate 409, faol guruhlar bilan deactivate 409, bog‘langan guruhlar bilan delete 409
- [x] 016 — Guruhlar va jadval boshqaruv API.
  - Qabul: teacher/subject mosligi, jadval/day/time/price/capacity validatsiyasi,
    CRUD/filter; bandlikdan past max_students belgilash rad etiladi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 57 fayl, 122 pytest passed; /api/v1/admin/groups teacher/subject mosligi (404/409/422), jadval/vaqt/kun/narx/capacity validatsiyasi, bandlikdan past capacity 409, CRUD, filtrlash va xavfsiz o‘chirish
- [x] 017 — Student/parent atomik CRUD va capacity nazorati.
  - Qabul: ikkalasini bir tranzaksiyada yaratish, deep linklar va parent detail,
    ko‘chirish/deactivate; parallel so‘rovlarda ham capacity oshmaydi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 60 fayl, 127 pytest passed; /api/v1/admin/students student/parent atomik yaratish, deep linklar va parent detail, capacity nazorati va parallel xavfsizlik, ko‘chirish va xavfsiz o‘chirish
- [x] 018 — Teacher uchun guruh va talaba read API.
  - Qabul: faqat o‘z guruhlari, talabalar va parent kontakt/Telegram holati;
    boshqa teacher IDlari bilan to‘g‘ridan-to‘g‘ri so‘rovlar rad etiladi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 63 fayl, 129 pytest passed; /api/v1/teacher guruhlar, talabalar va ota-onalar read API; teacher portal guard (admin/superadmin 403), ownership izolyatsiyasi (begona guruh/talaba 404), parent kontakt va Telegram status
- [x] 019 — Davomat draft API.
  - Qabul: teacher-only present/absent/late va note, group/student/date validatsiyasi,
    unique upsert; boshqa guruh va yakunlangan sana yozuvi rad etiladi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 65 fayl, 132 pytest passed; /api/v1/teacher/groups/{id}/attendance/draft teacher-only, present/absent/late va note (<=2000), begona talaba rad etilishi (422), unique upsert, yakunlangan sana rad etilishi (409)
- [x] 020 — Davomatni yakunlash va tarix API.
  - Qabul: barcha faol talabalar belgilanadi, idempotent finalization/outbox,
    Background Task; admin/superadmin sana/guruh/teacher filtrli tarixni ko‘radi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 67 fayl, 135 pytest passed; davomatni yakunlash (barcha faol talabalar shart - 422), idempotent finalization va atomic notification outbox (pending/skipped), Background Task, /api/v1/admin/attendance sana/guruh/teacher filtrli tarix API

## Telegram integratsiyasi

- [x] 021 — Superadmin bot sozlamalari va dinamik reload protokoli.
  - Qabul: getMe bilan token tekshirish, encryption, username/config version,
    faqat superadmin; boshlang‘ich token uchun hidden-input CLI,
    token API/loglarda yashiriladi, reload failure ko‘rinadi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 70 fayl, 142 pytest passed; /api/v1/admin/settings/bot superadmin-only (admin va teacher 403), getMe tekshirish, token encryption va API javobida token yashirilishi, reload status va last_error, neoavlod.cli set-bot-token --token-stdin
- [x] 022 — Bot worker va /start orqali hisob bog‘lash.
  - Qabul: staff/parent/student UUID tekshiruvi, telegram_id atomik saqlash,
    expired/used/invalid linklar; token yangilanganda eski polling yopiladi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 72 fayl, 150 pytest passed; link_telegram_account staff/parent/student UUID tekshiruvi, telegram_id atomik saqlash, expired/used/invalid/inactive rad etilishi, takroriy telegram_id oldini olish, process_telegram_update (/start va xabarlar), BotWorker va token yangilanganda eski polling yopilishi (dynamic reload)
- [x] 023 — Login/reset OTP Telegram yetkazish servisi.
  - Qabul: haqiqiy 6 raqam, hash storage, TTL/purpose va bir martalik consume,
    retry/429/timeout, delivery failureda session ochilmaydi; kod loglanmaydi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 73 fayl, 155 pytest passed; haqiqiy 6 raqamli OTP, HMAC-SHA256 hash storage (kod ochiq saqlanmaydi), 5 daqiqa TTL va purpose-binding (login/reset o‘zaro ishlamaydi), bir martalik consume va replay rad etilishi, TelegramClient retry/429/timeout, delivery failureda session ochilmasligi va kod hech qayerda loglanmasligi
- [x] 024 — Davomat notification outbox worker.
  - Qabul: o‘zbekcha talab qilingan xabar formati, parentga yuborish,
    ulanmagan parent holati, retry/backoff, restart va concurrent claim testlari.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 75 fayl, 162 pytest passed; o‘zbekcha davomat bildirishnomasi formati, ulangan parentga yuborish, ulanmagan parent (SKIPPED va ulanganida yetkazish), exponential backoff va retry, crashed worker leaseni tiklash (restart recovery) va PostgreSQL FOR UPDATE SKIP LOCKED bilan concurrent claim testlari
- [x] 025 — Backend integratsiya va xavfsizlik regressiyasi.
  - Qabul: real disposable PostgreSQLda auth/RBAC/capacity/finalization/reload
    testlari; Telegram fake; backend check va migration check to‘liq o‘tadi.
  - Dalil: Docker check_backend: compileall/Ruff/mypy 76 fayl, 165 pytest passed; real disposable PostgreSQLda bootstrap superadmin -> Telegram OTP login -> fan, o'qituvchi, guruh (capacity=2), talabalar atomik yaratish -> capacity limit (409) -> teacher davomat draft va finalize -> outbox notification yetkazish -> RBAC portal guard (403), CSRF (403), inactive staff (401) -> BotWorker dinamik reload (v1->v2) to'liq regressiya o'tdi; run_migrations va check_agent_skills to'liq o'tdi

## Frontend Admin

- [x] 026 — Frontend workspace va umumiy UI/API poydevori.
  - Qabul: ikkita Vite React TS ilova, Tailwind/Inter/lucide, UI package,
    cookie/CSRF API client, error/loading holatlar; ikkala build/typecheck/lint o‘tadi.
  - Dalil: Docker check_frontend: npm run typecheck (@neoavlod/ui, @neoavlod/admin, @neoavlod/teacher) va npm run lint (eslint flat config) muvaffaqiyatli o'tdi; npm run build ikkala Vite React TS ilovasini (admin va teacher) to'liq yig'di; @neoavlod/ui da Button, Input, Select, Card, Badge, Alert, Modal, Table, Spinner, LoadingState, ErrorState, EmptyState komponentlari; cookie va eduneo_csrf tokenni o'quvchi ApiClient yaratildi
- [x] 027 — Umumiy login, OTP va password recovery ekranlari.
  - Qabul: username/parol → Telegram OTP, reset OTP va eski parol bilan change,
    expiration/error UX, secretlar localStoragega yozilmaydi; flow testlari.
  - Dalil: Docker check_frontend: typecheck va lint muvaffaqiyatli o'tdi; vitest 4 ta flow test o'tdi (LoginForm credentials -> Telegram OTP tasdiqlash, OTP expiration UX ogohlantirishi, PasswordRecoveryModal orqali username -> Telegram OTP -> yangi parol tasdiqlash, PasswordChangeModal eski va yangi parol bilan change); qat'iy xavfsizlik tekshirildi (localStorage va sessionStorage ga secretlar yoki tokenlar yozilmaydi); ikkala ilova (admin va teacher) build o'tdi; check_backend (165 test) va check_agent_skills to'liq o'tdi
- [x] 028 — Admin shell, navigatsiya va permission routing.
  - Qabul: responsive sidebar/header, joriy user/permission, logout,
    teacher uchun 403 sahifasi; ruxsatsiz amallar UI da bloklanadi.
  - Dalil: Docker check_frontend: typecheck va lint muvaffaqiyatli o'tdi; vitest da 12 test o'tdi (AdminShell responsive sidebar/header, superadmin to'liq navigatsiya, limited admin uchun ruxsatsiz bo'limlar yashirilishi va to'g'ridan-to'g'ri kirish bloklanishi, teacher uchun 403 ForbiddenPage va portal o'tish havolasi, header/sidebar orqali logout); npm run build ikkala ilova uchun muvaffaqiyatli yakunlandi; check_backend (165 test) va check_agent_skills to'liq o'tdi
- [x] 029 — Staff va permission boshqaruv ekranlari.
  - Qabul: jadval/search/modal, staff CRUD, Telegram link/status,
    superadmin admin/permission boshqaradi; validation va API xatolari ko‘rinadi.
  - Dalil: Staff boshqaruv jadvallari, qidiruv va filtrlar, StaffModal (superadmin ruxsat tanlash va xodim yaratish/tahrirlash), TelegramLinkModal (deep link va rotatsiya), StaffManagementView hamda Admin app integratsiyasi amalga oshirildi. 20 ta vitest testlari, typecheck, lint, monorepo build va backend regressiyasi Docker orqali to‘liq muvaffaqiyatli o‘tdi. LocalStorage va sessionStorage xavfsizligi to‘liq saqlandi.
- [x] 030 — Subject va guruh boshqaruv ekranlari.
  - Qabul: CRUD, teacher/subject select, kun/vaqt/xona/narx/capacity,
    bandlik ko‘rsatkichi va permission holatlari; frontend check o‘tadi.
  - Dalil: Subject va guruh boshqaruv ekranlari to‘liq yaratildi: SubjectModal va SubjectsManagementView (fanlar CRUD, qidiruv, holat o‘zgartirish, o‘chirish tasdig‘i), GroupModal va GroupsManagementView (guruhlar CRUD, dars kunlari presetlari va checkboxlari, vaqtlar ketma-ketligi tekshiruvi, xona, narx, o‘qituvchi va fan tanlash, OccupancyBadge bandlik ko‘rsatkichi va RBAC permission cheklovlari). Admin App ga integratsiya qilindi. 30 ta vitest testlari, typecheck, lint, monorepo build va backend regressiyasi Docker orqali to‘liq o‘tdi. Storage xavfsizligi ta’minlandi.
- [x] 031 — Student/parent yaratish va detail drawer.
  - Qabul: bir formadan student/parent yaratish, guruh bandlik xatosi,
    telefonlar/Telegram status/deep linklar va ko‘chirish oqimi ishlaydi.
  - Dalil: Yagona formadan student va parent yaratish/tahrirlash (StudentModal), guruh to‘lganlik xatosi (409 Conflict alert), yangi guruhga ko‘chirish oqimi (StudentTransferModal), batafsil profil, telefonlar va Telegram ulanish holatlari hamda deep link rotatsiyalari (StudentDetailDrawer), umumiy jadval va filtrlar (StudentsManagementView) hamda Admin App integratsiyasi to‘liq amalga oshirildi. 38 ta vitest testlari, frontend typecheck, lint, monorepo build va backend regressiyasi Docker orqali muvaffaqiyatli o‘tdi. Storage xavfsizligi saqlandi.
- [x] 032 — Admin davomat tarixi ekrani.
  - Qabul: sana/guruh/teacher filtrlari, pagination, Bor/Yo‘q/Kechikdi va izoh,
    readonly jadval, empty/error/loading holatlar; davomat yozish amali yo‘q.
  - Dalil: Admin davomat tarixi ekrani yaratildi: sana/guruh/teacher/holat filtrlari, Bugun tugmasi, statistik ko‘rsatkichlar (Bor, Yo‘q, Kechikdi, Jami), AttendanceBadge, readonly jadval (hech qanday davomat olish yoki o‘zgartirish amali mavjud emas), finalized holati, izohlar ko‘rinishi va to‘liq pagination. Admin App ga integratsiya qilindi. 41 ta vitest testlari, typecheck, lint, production build va 165 ta backend testlari to‘liq muvaffaqiyatli o‘tdi. Storage xavfsizligi saqlandi.
- [x] 033 — Superadmin bot sozlamalari ekrani.
  - Qabul: token kiritish/almashtirish, username/connection/reload holati,
    maskalash; admin/teacher route va API orqali kira olmaydi.
  - Dalil: Superadmin bot sozlamalari ekrani to‘liq yaratildi: bot username, connection status, version va worker sinxronizatsiya/reload_in_progress indikatorlari, last_error qaydlari, parolli/maskalangan token input (show/hide toggle), tasdiqlash modali orqali yangilash, muntazam yangilash (poll/refresh) va qat’iy RBAC guard (admin va teacher 403 Forbidden alert bilan bloklanadi). Admin App ga integratsiya qilindi. 45 ta vitest testlari, typecheck, lint, monorepo production build va 165 ta backend testlari Docker orqali to‘liq o‘tdi. Storage xavfsizligi saqlandi.

## Frontend Teacher

- [x] 034 — Teacher shell, portal guard va o‘z guruhlari.
  - Qabul: alohida teacher build, auth/403 guard, faqat biriktirilgan guruhlar,
    jadval/bandlik ko‘rsatkichi va responsive navigation.
  - Dalil: TeacherShell va TeacherGroupsView komponentlari yaratildi; admin/superadmin uchun 403 ForbiddenPage guard va https://admin.eduneo.uz havolasi ta’minlandi; o‘qituvchiga biriktirilgan guruhlar, jadvallar, OccupancyBadge bandlik ko‘rsatkichlari, qidiruv va filtrlar ishga tushirildi; alohida teacher Vite production build muvaffaqiyatli yakunlandi; vitest 54 ta test, typecheck, lint, monorepo build va 165 ta backend testlari to‘liq o‘tdi. Storage xavfsizligi saqlandi.
- [x] 035 — Teacher talaba va ota-ona detail UI.
  - Qabul: o‘z guruhi talabalari, drawerda parent telefon/Telegram status,
    unauthorized/empty/loading/error holatlar; boshqa guruhga kirish bloklanadi.
  - Dalil: TeacherGroupStudentsView va TeacherStudentDetailDrawer komponentlari yaratildi; guruh talabalari ro‘yxati, qidiruv va filtrlar, batafsil drawerda talaba va ota-ona telefonlari hamda Telegram ulanish holatlari (ulanganida yashil xabarnoma statusi, ulanmaganida ogohlantirish) ko‘rsatildi; boshqa yoki begona guruhga kirishda 404/403 unauthorized himoya va qaytish imkoniyati berildi; Teacher App ga to‘liq integratsiya qilindi. 63 ta vitest testlari, typecheck, lint, monorepo build va 165 ta backend testlari to‘liq muvaffaqiyatli o‘tdi. Storage xavfsizligi saqlandi.
- [x] 036 — Teacher davomat belgilash va yakunlash UI.
  - Qabul: Bor/Yo‘q/Kechikdi, har talabaga izoh, draft saqlash va yakunlash,
    yakunlangan readonly holat; duplicate click va API xatosi testlari.
  - Dalil: TeacherAttendanceView komponenti yaratildi: Bor/Yo‘q/Kechikdi 3-holatli belgilash, har bir talabaga izoh kiritish (<=2000 belgi), barchasini 'Bor' qilish tezkor amali, qoralama saqlash (POST /draft) va yakunlash (POST /finalize); yakunlashdan oldin barcha talabalar belgilanishi shartligi validatsiyasi va modal ogohlantirish; yakunlangan varaqani qat’iy readonly holatga o‘tkazish (barcha tugmalar disabled, izohlar text ko‘rinishida); duplicate click himoyasi va API xatoliklari (409 conflict, 422, tarmoq xatolari) boshqaruvi; Teacher App ga to‘liq integratsiya qilindi. 71 ta vitest testlari, typecheck, lint, monorepo build va 165 ta backend testlari to‘liq muvaffaqiyatli o‘tdi. Storage xavfsizligi saqlandi.
- [x] 037 — Frontend E2E, accessibility va dizayn tekshiruvi.
  - Qabul: ikkala portal login/reset/RBAC va asosiy CRUD/davomat oqimlari,
    keyboard/focus/modal/mobile tekshiruvi; emoji yo‘q; build/typecheck/lint o‘tadi.
  - Dalil: Ikkala portal (Admin va Teacher) login, reset, change password, RBAC routing va asosiy CRUD/davomat oqimlari (staff, subject, group, student/parent atomic CRUD, teacher draft & finalization, admin attendance history) to‘liq E2E va flow testlari bilan tekshirildi; Modal va Drawer keyboard (Escape), ARIA (dialog, aria-modal, aria-label) va body overflow tozalanishi hamda AdminShell va TeacherShell mobile hamburger drawer ochilish/yopilish navigatsiyasi tekshirildi; frontend kod bazasida qat’iy nol emoji mavjudligi tasdiqlandi; 83 ta vitest testlari, typecheck, lint, ikkala Vite ilovasi production build va 165 ta backend testlari to‘liq muvaffaqiyatli o‘tdi. Storage xavfsizligi saqlandi.

## Infratuzilma va deployment

- [x] 038 — Production Docker API va Telegram worker konfiguratsiyasi.
  - Qabul: nonroot multi-stage backend image, compose healthcheck/persistent volume,
    secrets/env, worker singleton; disposable muhitda start/stop smoke o‘tadi.
  - Dalil: Production Docker multi-stage runtime (UID 1000 app nonroot), compose.prod.yaml (database pg 18.6 persistent volume, migrations alembic upgrade head, api healthcheck, worker singleton replicas: 1), .env.production.example va neoavlod.cli worker (--once va unified loop) yaratildi; smoke_prod_docker.sh orqali disposable start/stop, database health, migration exit 0, api /api/v1/health va /api/v1/ready 200 OK hamda worker singleton to'liq tasdiqlandi; 166 pytest, check_frontend va check_agent_skills to'liq o'tdi.
- [x] 039 — Nginx subdomen, statik frontend va TLS konfiguratsiyasi.
  - Qabul: admin.eduneo.uz/teacher.eduneo.uz SPA fallback, `/api` proxy,
    xavfsiz cookie/header, rate/body limits; nginx -t va portal smoke o‘tadi. backend: api.eduneo.uz da ishlashi kerak.
  - Dalil: Nginx konfiguratsiyasi yaratildi: admin.eduneo.uz va teacher.eduneo.uz (SPA routing fallback try_files, /api/ reverse proxy, static assets caching va xavfsiz headerlar), api.eduneo.uz (to'g'ridan-to'g'ri backend proksi, rate limit va 10m client_max_body_size), HTTP->HTTPS 301 redirect va zamonaviy TLS HTTP/2; smoke_nginx.sh orqali nginx -t, portallar SPA fallback, xavfsizlik headerlari, kesh, API proxy hamda 413 body cheklovi to'liq tasdiqlandi; check_backend, check_frontend va check_agent_skills to'liq o'tdi.
- [x] 040 — GitHub Actions CI/CD va rollback deployment.
  - Qabul: backend/frontend/migration testlari, npm ci/build, belgilangan server
    kataloglariga artifact deploy, pinned SSH host, health check va release rollback.
  - Dalil: GitHub Actions CI/CD (.github/workflows/ci-cd.yaml) poydevori yaratildi: PostgreSQL 18.6 servisli backend sifat darvozasi (ruff, mypy, alembic, pytest), Node 22 frontend sifat darvozasi (npm ci, typecheck, lint, test, build), pinned SSH host orqali xavfsiz deployment, skriptlar to'plami (deploy.sh, rollback.sh, remote_deploy.sh); smoke_cicd_rollback.sh orqali YAML sintaksisi, atomik simvolik havolalar (releases -> current), muvaffaqiyatsiz deployda avtomatik rollback, qo'lda rollback hamda retention (5 ta release) to'liq tasdiqlandi; check_backend, check_frontend va check_agent_skills to'liq o'tdi.
- [x] 041 — Ubuntu DEPLOYMENT.md va yakuniy acceptance.
  - Qabul: DNS/TLS/env/DB/migrate/bootstrap/bot/CI secrets/deploy ko‘rsatmalari,
    backup/restore/rollback, toza muhit smoke va to‘liq biznes flow checklist;
    haqiqiy serverga chiqarish faqat mavjud credentials/foydalanuvchi doirasida.
  - Dalil: DEPLOYMENT.md qo‘llanmasi (DNS/TLS/env/DB/migrate/bootstrap/bot/CI secrets/deploy/backup/restore/rollback va to‘liq 10 bandli biznes flow checklist) yaratildi; smoke_clean_environment.sh orqali toza muhitda PostgreSQL 18.6, Alembic migratsiyalari, superadmin bootstrap CLI (--password-stdin), bot token CLI (--token-stdin), background worker singleton (--once), API /health va /ready (200 OK) hamda pg_dump zaxirasi to‘liq tasdiqlandi; check_backend (166 test), check_frontend va check_agent_skills to‘liq o‘tdi.

- [x] 042 — Local frontend va demo hisoblarini ishga tushirish.
  - Qabul: Dockerda API/admin/teacher ishlaydi; alohida demo DBda superadmin va teacher hisoblari foydalanuvchi so‘ragan local parol bilan yaratiladi; OTP local ekranda ko‘rinadi; ikkala portal login va teacher guruh oqimi tekshiriladi; production factory demo endpoint bermaydi.
  - Dalil: 2026-10-05: local_demo.sh up/smoke — isolated demo DB migrations/head check, idempotent seed, API/admin/teacher Docker services active; both portal OTP login, role data and CSRF logout passed. Browser: superadmin login and teacher 3-student attendance draft save passed. Docker check_backend: Ruff/mypy and 169 tests; frontend typecheck/lint, 85 tests and both builds passed; check_agent_skills: 13 tests and 42-task invariants passed. Production/default factory demo endpoint absent, production/test/non-demo DB rejected.

- [x] 043 — Ubuntu deployment va CI/CDni to‘g‘rilash.
  - Qabul: /root/NeoAvlodLMS SSH clone va ikki yo‘nalish SSH sozlash; local Docker frontend build Gitga kiritiladi va CI stale/tampered buildni rad etadi; main push exact SHA backend/frontend deploy qiladi; /var/www/neoavlod statik fayllar, versioned backend image, DB backup/migration, failure/manual rollback, webroot TLS va yagona sertifikat yo‘llari; Docker regressiya va real disposable deploy smoke. VPS/Actions tekshiruvi credentials mavjud bo‘lganda bajariladi, local dalildan farqlanadi.
  - Dalil: 2026-10-05: Docker check_backend Ruff/mypy + 169 pytest; frontend release Docker install/typecheck/lint/85 tests/both production builds and prepare-release --check passed; run_migrations head/model match; actionlint + 8 deployment regressions and deployment-script Ruff/bash syntax passed; Nginx 1.24 portal smoke passed; real disposable PostgreSQL/API/worker/TLS deployment A->B, failed Nginx C auto rollback B, manual rollback A, exact image+both portal SHA and pg_restore backup list passed. check_agent_skills 13 tests/43-task invariants passed. Ubuntu SSH clone/CI key/DNS/webroot TLS/bootstrap/update/backup guide updated for root@189.74.99.79. Actual VPS/Actions/Telegram validation not run: pinned host identity and CI/environment setup still required; supplied VPS password was not stored.

- [x] 044 — Ubuntu Nginx server_names_hash va ACME bootstrap regressiyasi.
  - Qabul: repo http kontekstida hash bucket 64; Ubuntu host nginx.conf sozlash qo‘llanmada TLSdan oldin; nginx -t muvaffaqiyatli bo‘lsagina reload; uch domen uchun bootstrap va production ACME 200/404 smoke Dockerda; local demo tiklanadi. Haqiqiy VPS natijasi foydalanuvchi terminalida alohida tasdiqlanadi.
  - Dalil: 2026-10-05: Docker Nginx 1.24 nginx -t passed with explicit http server_names_hash_bucket_size 64. Bootstrap before TLS and production HTTP verified actual ACME 200/content and missing-file 404 for admin/teacher/api; redirects, SPA/security headers, static cache, API health/ready proxy and 413 limit passed. check_agent_skills: 13 tests, shell syntax and 44-task invariants passed. Local demo restart returned healthy services. Ubuntu host nginx.conf backup/edit step added before TLS; reload guarded by nginx -t. VPS configuration/result must be confirmed in user terminal; host nginx.conf is not overwritten by release scripts.

- [x] 045 — Haqiqiy Telegram bot orqali login: Redis OTP, bot username sozlamasi, ulanmagan xodim holati.
  - Qabul: OTP faqat Redisda (hash, TTL 300s, 5 urinish, bir martalik, almashtirish/parol o‘zgarishida bekor qilish); `otp_challenges` jadvali olib tashlanadi; local demo OTP ekranda ko‘rsatish endpointi va UI olib tashlanadi; superadmin sozlamalarida bot username maydoni va u bo‘yicha xodim havolasi generatsiyasi (token shart emas); frontend `TelegramLinkState` backend bilan mos; Telegramga ulanmagan xodim login sahifasida "Telegram botga hali ulanmagan" xabarini oladi; local muhitda redis + bot worker + haqiqiy bot (token DBda shifrlangan) bilan login Dockerda tekshiriladi.
  - Dalil: OTP faqat Redisda (TTL 300s, max 5 urinish, atomik Lua bir martalik consume va almashtirishda bekor qilish), otp_challenges jadvali 0003 migratsiyasi bilan o'chirildi. Local OTP ekranda ko'rsatish endpointi va UI olib tashlandi. Bot username sozlamasi (PUT /api/v1/admin/settings/bot/username) va TelegramLinkState yangilandi, xodim havolasi token talab qilmasdan generatsiya qilinadi. Telegramga ulanmagan xodimga 'Telegram botga hali ulanmagan' xabari chiqariladi. Dockerda check_backend (168 test, Ruff, mypy), check_frontend (typecheck, lint, 93 vitest test), run_migrations, check_agent_skills (13 test) va local_demo up/smoke to'liq muvaffaqiyatli o'tdi.

## LMS yaxshilanishlari — 2026-10-08

### Umumiy qabul qoidalari

- Quyidagi ishlar 045 dan keyin ID tartibida, bittadan bajariladi. Mavjud
  auth/RBAC, CRUD, OTP va davomat imkoniyatlari kengaytiriladi; yakunlangan
  vazifalar qaytadan yaratilmaydi. 045 dagi Redis OTP qarori yuqoridagi eski
  DB OTP arxitektura tavsifidan ustun turadi.
- Backend o‘zgarsa `check_backend.sh`, schema o‘zgarsa `run_migrations.sh`;
  frontend o‘zgarsa `check_frontend.sh`, Dockerda tegishli flow testlari va
  ikkala portal buildi; reestr o‘zgarsa `check_agent_skills.sh` bajariladi.
  Har bir vazifa dalilida aniq buyruq, natija va amaliy acceptance qayd etiladi.
- «Professional UI»: bir xil Inter shriftlari, ranglar, spacing, tugma/input/
  modal/jadval uslublari; lucide-react ikonkalari; 360px mobil, 768px planshet
  va 1440px desktopda kesilmagan kontent. Keyboard, focus, ARIA, loading,
  empty, error va muvaffaqiyat holatlari tekshiriladi. Rangning o‘zi statusni
  anglatmaydi; ikonkaga matn yoki accessible label ham qo‘shiladi.
- UI atamalari: «Dashboard», «Xodimlar», «O‘quvchilar», «Davomat»;
  davomat statuslari «Keldi», «Kech qoldi», «Kelmadi». API enumlari va
  `/students` yo‘llarining nomini faqat matn almashtirish uchun o‘zgartirmaslik.
- Oy Asia/Tashkent bo‘yicha hisoblanadi; joriy oy standart tanlov bo‘ladi.
  Statistikaga faqat yakunlangan davomat kiradi. «Kelgan» = Keldi + Kech qoldi;
  kechikish alohida ham ko‘rsatiladi. Qoralama, belgilanmagan sana va dars
  bo‘lmagan kun «Kelmadi»ga avtomatik qo‘shilmaydi. Tarixiy yozuvlar o‘quvchi
  guruhdan ko‘chirilganda yo‘qolmaydi; teacher faqat ruxsatli guruh yozuvini ko‘radi.
- Foydalanuvchiga kerak bo‘lmagan texnik/takroriy izohlar olib tashlanadi;
  form label, validatsiya, muhim ogohlantirish va amallar tasdig‘i saqlanadi.

### Xodim yaratish va Telegram orqali kirish ma’lumotlari

- [x] 046 — Xodim yaratishda avtomatik vaqtinchalik parol API.
  - Manba: talab 1. Bog‘liq: 045.
  - Qabul: staff create API qo‘lda parol kiritishni talab qilmaydi; server
    kriptografik xavfsiz generator bilan mavjud kuchlilik siyosatiga mos parol
    yaratadi va auth uchun Argon2 hash saqlaydi. Yetkazilishi kutilayotgan
    vaqtinchalik parol alohida shifrlangan holda, cheklangan muddat bilan
    saqlanadi; oddiy staff list/detail javoblari, audit va loglarda ochilmaydi.
    Parolni yangilash kerakligini bildiruvchi holat mavjud; change/reset
    bajarilganda bu holat va eski onboarding credential bekor qilinadi.
    Mavjud xodimlarning amaldagi parollari o‘zgarmaydi; create RBAC saqlanadi.
  - Tekshiruv: generation/hash, encrypted storage/expiry, javob va loglarda
    secret yo‘qligi, change/reset cleanup, RBAC va migratsiya Dockerda o‘tadi.
  - Dalil: Alembic 0004 migratsiyasi bajarildi; Staff modeliga must_change_password, temporary_password_encrypted, temporary_password_expires_at qo‘shildi; staff create API da parol kiritilmaganda 14 belgili xavfsiz vaqtinchalik parol yaratilib Fernet bilan shifrlanadi va 3 kunlik muddat beriladi, Argon2 hash saqlanadi; javoblarda (StaffOut/StaffDetail) maxfiy ma’lumotlar oshkor qilinmaydi; parol o‘zgartirilganda yoki reset qilinganda must_change_password False bo‘lib shifrlangan vaqtinchalik parol tozalanadi; Docker backend (169 test), frontend va skill testlari to‘liq o‘tdi.

- [x] 047 — Bot /start orqali xodimni bog‘lash va login/parolni yetkazish.
  - Manba: talab 1. Bog‘liq: 045, 046.
  - Qabul: admin bergan `staff_<uuid>` deep link bilan shaxsiy chatda /start
    bosilganda xodimning Telegram IDsi bir martalik atomik bog‘lanadi; bot
    tegishli portal havolasi, username, vaqtinchalik parol va «Parolingizni
    yangilab qo‘ying» ogohlantirishini beradi. Oddiy /start noma’lum odamga
    boshqa xodim credentialini bermaydi. Noto‘g‘ri/eskirgan/ishlatilgan link,
    boshqa hisobga qayta bog‘lash va faol bo‘lmagan xodim rad etiladi.
    Yetkazish xatosida credential yo‘qolmaydi, retry/restart oqimi ishlaydi;
    tasdiqlangan yetkazishdan keyin shifrlangan parol o‘chiriladi. Takroriy
    /start saqlanmagan parolni oshkor qilmaydi, reset yo‘lini tushuntiradi.
    Telegram timeoutidagi qayta yuborish ehtimoli aniq hujjatlashtiriladi.
  - Tekshiruv: fake Telegram bilan binding/concurrency/retry/cleanup testlari;
    Docker worker va haqiqiy botda yangi xodimga yetkazish → web login/OTP →
    parolni yangilash tasdiqlanadi, secretlar dalilda yozilmaydi.
  - Dalil: Telegram /start staff_<uuid> orqali xodimning Telegram IDsi bir martalik atomik bog‘lanadi; bot tegishli portal havolasi, username, vaqtinchalik parol va parolni yangilash haqidagi ogohlantirishni yuboradi; tasdiqlangan yetkazishdan keyin shifrlangan vaqtinchalik parol DB dan o‘chiriladi; yetkazish xatosida tranzaksiya rollback qilinadi va credential saqlanib qoladi; takroriy /start yoki oddiy /startda parol oshkor qilinmaydi va reset tartibi tushuntiriladi; Telegram timeout ehtimoli hujjatlashtirildi; Docker backend (172 test), frontend va skill testlari muvaffaqiyatli o‘tdi.

- [x] 048 — Xodimlar bo‘limini professional boshqaruv ekraniga keltirish.
  - Manba: talablar 1, 3. Bog‘liq: 046, 047.
  - Qabul: create modalidan qo‘lda parol maydoni olib tashlanadi; avtomatik
    parol va Telegram orqali olish tartibi qisqa tushuntiriladi. Yaratishdan
    keyin onboarding havolasini ochish/nusxalash va ulanish holati ko‘rinadi.
    Jadvalda F.I.Sh., login, rol, aloqa, faollik va Telegram holati aniq;
    qidiruv, rol/holat filtri, pagination, create/edit/deactivate amallari
    tushunarli. Superadmin admin/teacher va permissionlarni qulay boshqaradi;
    oddiy admin cheklovlari, oxirgi superadmin himoyasi va API xatolari saqlanadi.
  - Tekshiruv: create → link → holat, edit/permission/deactivate flowlari,
    duplicate submit himoyasi, mobil/desktop ko‘rinish Dockerda tekshiriladi.
  - Dalil: Xodim yaratish modalidan qo‘lda parol kiritish maydoni olib tashlandi va avtomatik parol hamda Telegram bot orqali olish tartibi haqida tushuntirish berildi; xodim yaratilgach Telegram onboarding havolasi modali avtomatik ochilib, havola, nusxalash, Telegramda ochish va ulanish holati ko‘rsatiladi; jadvalda F.I.Sh, login, rol, aloqa, faollik va Telegram holati, filtrlash, qidiruv va pagination professional holatga keltirildi; duplicate submit himoyasi ishlaydi; Docker frontend (93 test, typecheck, eslint), backend (172 test) va skill testlari to‘liq o‘tdi.

### Shaxsiy profil, parol va rasm

- [x] 049 — Barcha xodimlar uchun o‘z profilini tahrirlash API.
  - Manba: talab 4. Bog‘liq: 046.
  - Qabul: superadmin, admin va teacher uchun joriy profilni olish hamda
    F.I.Sh./telefon kabi mavjud tahrirlanadigan maydonlarni yangilash API
    ishlaydi. Username tahriri mavjud uniqueness/login qoidalariga mos.
    Self-service orqali rol, permissions, status, Telegram ID yoki boshqa
    xodim profili o‘zgartirilmaydi. Validatsiya, duplicate 409, CSRF/session
    va inactive himoyasi mavjud; auth identity javobi yangilangan profilga mos.
  - Tekshiruv: uch rolning o‘z profilini yangilashi, begona hisob va himoyalangan
    maydonlar rad etilishi, uniqueness va mavjud auth regressiyasi Dockerda o‘tadi.
  - Dalil: PATCH /api/v1/auth/{portal}/me self-profile endpointi amalga oshirildi; superadmin, admin va teacher o‘z ism, familiya, telefon va usernameni xavfsiz tahrirlay oladi; username va telefon uniqueness qoidasi 409 qaytaradi; role, permissions, status, telegram_id kabi maydonlarni o‘zgartirish 422 bilan rad etiladi; begona portal va inactive hisoblar 403 bilan to‘siladi; CSRF va Origin tekshiruvlari o‘rnatildi; Docker backend (177 test), frontend va skill testlari to‘liq o‘tdi.

- [x] 050 — Profil rasmini yuklash, almashtirish va o‘chirish API.
  - Manba: talab 4. Bog‘liq: 049.
  - Qabul: barcha uch rol o‘z avatarini yuklaydi/almashtiradi/o‘chiradi;
    fayl turi, haqiqiy image kontenti va hajm limiti serverda tekshiriladi.
    Tasodifiy fayl nomi, xavfsiz media URL, eski faylni tozalash va avatarsiz
    fallback mavjud. Rasm Docker/production restartidan keyin saqlanadi;
    persistent storage, media route/proxy va backup tartibi hujjatlashtiriladi.
    Begona xodim rasmini almashtirish va fayl yo‘li orqali chiqish rad etiladi.
  - Tekshiruv: upload/replace/delete, noto‘g‘ri va katta fayl, ownership,
    migratsiya hamda restartdan keyin media olish Dockerda tekshiriladi.
  - Dalil: 0005_staff_avatar_url migratsiyasi qo‘shildi; POST va DELETE /api/v1/auth/{portal}/avatar orqali barcha uch rol uchun yuklash, almashtirish va o‘chirish amalga oshirildi; PNG, JPEG va WebP magic bytes va 5 MB limit (413/422) serverda tekshiriladi; tasodifiy nom va eski fayllarni tozalash o‘rnatildi; /media/avatars/{filename} xavfsiz routing va traversal himoyasi bilan xizmat ko‘rsatadi; Nginx /media/ proxy va compose.prod.yaml media-data volume sozlandi; 181 backend test, frontend typecheck/lint, 93 frontend test, migratsiya va smoke_nginx muvaffaqiyatli o‘tdi.

- [x] 051 — Admin va teacher portallarida profil va parol boshqaruvi UI.
  - Manba: talab 4. Bog‘liq: 049, 050.
  - Qabul: superadmin/admin/teacher headerdan «Profilim»ni ochadi; profilni
    tahrirlash, avatar preview/yuklash/almashtirish/o‘chirish backendga ulangan.
    Eski parol bilan change password va «Parolni unutdingizmi?» orqali Telegram
    OTP reset mavjud auth API bilan ishlaydi. Parol confirmation va validatsiya,
    API xatosi va loading holati ko‘rinadi; change/resetdan keyin session
    bekor qilinishi foydalanuvchiga tushuntirilib login ekraniga yo‘naltiriladi.
    Vaqtinchalik parolli xodimga yangilash eslatmasi holatga qarab ko‘rsatiladi;
    muvaffaqiyatdan keyin olib tashlanadi. Avatar headerda ham yangilanadi.
  - Tekshiruv: uch rol uchun profil/avatar/change/reset oqimlari, noto‘g‘ri
    eski parol, OTP expiry, session revoke va mobil modallar tekshiriladi.
  - Dalil: UserProfileModal komponenti yaratildi va Admin hamda Teacher portallariga integratsiya qilindi; header va sidebarda avatar va "Profilim" tugmasi joylashtirildi; profil tahrirlash (PATCH /me), avatar yuklash/almashtirish/o‘chirish (POST/DELETE /avatar) ulandi; eski parol bilan change password va Telegram OTP reset modallari integratsiya qilindi; vaqtinchalik parolli xodimlar uchun eslatma banneri qo‘shildi; 181 backend test, 100 frontend test (user-profile-modal.test.tsx bilan), frontend typecheck/lint va migratsiyalar Dockerda to‘liq o‘tdi.

### Brending, admin navigatsiyasi va Dashboard

- [x] 052 — NeoAvlod logosini ikkala login va portalga bir xil ulash.
  - Manba: talab 5. Bog‘liq: mavjud logo assetlari va umumiy UI paketi.
  - Qabul: mavjud NeoAvlod logosi tekshirilib bitta umumiy komponent orqali
    admin/teacher login, OTP/reset ekranlari va portal header/sidebarida
    sifatli ko‘rsatiladi. Aspect ratio, kontrast, alt matn va mobil o‘lchamlar
    mos; production build/base pathda asset 404 bermaydi. Repozitoriydagi
    tugallanmagan logo o‘zgarishlari tekshiriladi, tasdiqsiz tayyor hisoblanmaydi.
  - Tekshiruv: ikkala Docker portalida login va ichki ekranlar, production
    asset yuklanishi, 360px/1440px o‘lchamlar vizual tasdiqlanadi.
  - Dalil: NeoAvlodLogo umumiy komponenti (NeoAvlodLogo, NeoAvlodLogoMark) yaratildi; admin/teacher login ekranlari, OTP va reset/change modallari, UserProfileModal hamda AdminShell va TeacherShell header va sidebarlariga bir xil ulashildi; SVG mark aspect ratio, gradientlar, accessibility (role="img", aria-label), mobil o‘lchamlar (xs..xl) ta’minlandi; neoavlod-logo.svg va favikonlar static public assetlar bilan bog‘landi; 14 vitest test fayli (100 test), check_frontend (typecheck va lint), production build (admin va teacher), check_backend (181 test, Ruff, mypy), run_migrations va smoke Dockerda to‘liq o‘tdi.

- [x] 053 — Admin shell, yig‘iladigan sidebar va keraksiz matnlarni tozalash.
  - Manba: talab 3. Bog‘liq: 052.
  - Qabul: desktop sidebar keng/ixcham rejimga ochilib-yopiladi; ixcham
    rejimda haqiqiy lucide ikonkalari va accessible nom/tooltip mavjud.
    Mobil sidebar overlay, yopish tugmasi, Escape va navigatsiyadan keyin
    yopilish bilan ishlaydi. Aktiv bo‘lim, header/profil menyusi va layout
    uyg‘un; «Bosh sahifa» barcha admin kirish nuqtalarida «Dashboard»ga
    almashtiriladi. Barcha admin ekranlaridagi takroriy/texnik matnlar
    tozalanadi, umumiy komponentlar uslubi muvofiqlashtiriladi; RBAC saqlanadi.
  - Tekshiruv: desktop collapse/expand, mobil open/close, keyboard/focus,
    permission navigation va admin ekranlari vizual ko‘rigi o‘tadi.
  - Dalil: AdminShell desktop yig‘iladigan (collapsible w-64/w-20) rejim, localStorage xotirasi, ixcham holatda markazlashgan Lucide ikonkalari, accessible nom va tooltiplar bilan jihozlandi; mobil sidebar overlay, yopish tugmasi, Escape klavishi va navigatsiyadan so‘ng yopilish bilan ta’minlandi; "Bosh sahifa" barcha admin kirish nuqtalarida va xatolik ekranlarida "Dashboard" / "Dashboardga qaytish"ga almashtirildi; dummy demo modal va texnik matnlar olib tashlandi; 102 frontend vitest testi (shu jumladan collapse/expand va Escape testlari), typecheck, eslint, production build, 181 backend testi, migratsiyalar va agent skills testlari Dockerda muvaffaqiyatli o‘tdi.

- [x] 054 — Dashboard uchun guruh, o‘quvchi va xodim statistikasi API/UI.
  - Manba: talab 3. Bog‘liq: 053.
  - Qabul: server barcha sahifalardan mustaqil to‘g‘ri umumiy sonlarni
    hisoblaydi; Dashboardda «Guruhlar», «O‘quvchilar», «Xodimlar» kartalari
    haqiqiy API ma’lumotlari bilan ko‘rinadi. Standart sonlar faol yozuvlar
    bo‘yicha, UI «Faol» deb aniq belgilaydi; xodimlar superadmin/admin/teacher
    jami. Superadmin uchalasini ko‘radi, cheklangan admin faqat tegishli
    permissiondagi ko‘rsatkichlarni oladi; yashirin ma’lumot API orqali ham
    ochilmaydi. Loading/empty/error va qayta yuklash mavjud, soxta sonlar yo‘q.
  - Tekshiruv: noldan/nonzero holat, yaratish/faolsizlantirishdan keyingi
    yangilanish, paginationdan mustaqil count va RBAC Dockerda tekshiriladi.
  - Dalil: GET /api/v1/admin/dashboard/stats API yaratildi; paginationdan mustaqil SQL COUNT orqali faol guruhlar (is_active=True), faol o‘quvchilar (status=active), va faol xodimlar (jami + teachers/admins/superadmins breakdown) hisoblanishi joriy etildi; RBAC doirasida ruxsatsiz sonlar null qilib yashirildi (superadmin to‘liq, cheklangan admin faqat o‘z permissioni); DashboardStatsCards komponenti yaratilib Admin App dashboardiga integratsiya qilindi; loading skeleton, error retry, empty holat va tezkor bo‘limga o‘tish tugmalari ta’minlandi; 185 backend testi (4 ta yangi test_dashboard_stats.py testi bilan), 106 frontend vitest testi (4 ta yangi dashboard-stats.test.tsx testi bilan), typecheck, lint, production build va agent skills testlari Dockerda to‘liq o‘tdi.

### O‘quvchilar va oylik profil statistikasi

- [x] 055 — Admin va teacher UI atamalarini «O‘quvchilar»ga o‘zgartirish.
  - Manba: talab 2. Bog‘liq: 053.
  - Qabul: mavjud «Talablar»/«Talabalar»/«Talaba» yozuvlari navigatsiya,
    sahifa sarlavhasi, jadval, forma, modal, empty/error va davomat ekranlarida
    mos ravishda «O‘quvchilar»/«O‘quvchi» bo‘ladi; ikki portal izchil.
    «Talablar» kabi boshqa ma’nodagi so‘zlar ko‘r-ko‘rona almashtirilmaydi;
    API, DB va permission kalitlari saqlanadi.
  - Tekshiruv: UI matnlari qidiruvi va ikkala portal ekranlari ko‘rigi;
    matnga bog‘liq mavjud flow testlari ham o‘tadi.
  - Dalil: Admin va teacher UI atamalaridagi talaba/talabalar so‘zlari kontekstga ko‘ra o‘quvchi/o‘quvchilar shakliga izchil o‘zgartirildi (navigatsiya, sarlavha, jadval, drawer, modal, empty/error, filter va davomat matnlari). RBAC permission kalitlari (students:read/create/edit), API yo‘llari va xavfsizlik talablari matnlari o‘zgarishsiz saqlandi. 106 frontend vitest testlari yangilangan matnlarga moslashtirilib to‘liq o‘tdi. Dockerda check_frontend, check_backend (185 pytest), run_migrations, check_agent_skills va build to‘liq muvaffaqiyatli yakunlandi.

- [x] 056 — O‘quvchi detail APIga oylik davomat statistikasini qo‘shish.
  - Manba: talablar 2, 8. Bog‘liq: 055.
  - Qabul: admin/teacher detail uchun oy tanlovi bilan Keldi, Kech qoldi,
    Kelmadi, jami kelgan va jami yakunlangan dars soni qaytariladi; yuqoridagi
    oy/status qoidalari qo‘llanadi. F.I.Sh., yosh, telefon, holat, guruh, fan,
    o‘qituvchi, jadval va ota-ona/Telegram ma’lumotlari portal ruxsatlari
    doirasida olinadi. Admin students:read, davomat qismi attendance:read
    bilan; teacher ownership orqali himoyalanadi. Davomat ruxsati bo‘lmagan
    adminda statistika yashiriladi, profil qoladi. Parol/token oshkor qilinmaydi.
  - Tekshiruv: aralash status, bo‘sh oy, oy/yil chegarasi, qoralama,
    guruhdan ko‘chirish va begona teacher/admin permission holatlari Dockerda.
  - Dalil: Admin va teacher student detail endpointlariga oy tanlovi (?month=YYYY-MM) bilan oylik davomat statistikasi (present_count, late_count, absent_count, attended_count, total_lessons) qo‘shildi; qoralamalar chiqarib tashlanib faqat finalized batch darslari hisoblanishi ta’minlandi; guruh, fan, o‘qituvchi va jadval (hafta kunlari, boshlanish/tugash vaqti, xona, narx) ma’lumotlari detail javobiga kiritildi; RBAC doirasida attendance:read huquqiga ega bo‘lmagan adminda profil qaytarilib statistika null qilib yashirildi; teacher ownership orqali begona talaba 404 berishi kafolatlandi; 193 backend testi (8 ta yangi test_student_monthly_stats.py testi bilan), 106 frontend vitest testi, check_frontend (typecheck, lint), check_backend (Ruff, mypy), run_migrations va check_agent_skills Dockerda to‘liq o‘tdi.

- [x] 057 — Ikki portalda to‘liq o‘quvchi profili va oylik statistika modali.
  - Manba: talablar 2, 8. Bog‘liq: 056.
  - Qabul: ro‘yxatdagi o‘quvchi satri yoki ismi bosilganda drawer o‘rniga
    professional modal ochiladi. Profil, guruh/dars, ota-ona/aloqa va Telegram
    bo‘limlari barcha mavjud ruxsatli ma’lumotni tartibli ko‘rsatadi;
    mavjud admin edit/transfer/link amallari permissionga mos saqlanadi.
    Oy tanlovi va «Kelgan», «Kech qoldi», «Kelmagan» ko‘rsatkichlari haqiqiy
    APIga ulangan; loading/empty/error va ruxsatsiz statistika holati mavjud.
    Modal scroll, Escape, focus trap/return va mobil ekran bilan ishlaydi;
    satrdagi boshqa amal tasodifan profilni ochmaydi.
  - Tekshiruv: admin/teacher row click va keyboard open, oy almashtirish,
    API ma’lumotlari, RBAC hamda 360px/768px/1440px ko‘rinish tasdiqlanadi.
  - Dalil: StudentProfileModal va TeacherStudentProfileModal yaratildi va drawerlar o‘rniga professional modalga almashtirildi; o‘quvchi profili, guruh va dars tafsilotlari (fan, o‘qituvchi, dars kunlari, vaqti, xona, oylik to‘lov), ota-ona aloqalari va Telegram integratsiyasi tartibli joylashtirildi; oylik davomat statistikasi (Kelgan, Kech qoldi, Kelmagan, jami darslar, davomat foizi) haqiqiy APIga ulandi va oy navigatsiyasi (oldingi/keyingi, input type="month") ta’minlandi; ruxsat yo‘q bo‘lganda profil saqlanib davomat ogohlantirishi berilishi va table row clickda amallar to‘xtatilishi (stopPropagation) joriy etildi; 16 vitest test fayli (115 test), check_frontend (typecheck va lint), check_backend (193 pytest, Ruff, mypy), run_migrations, build va check_agent_skills Dockerda to‘liq o‘tdi.

### Teacher davomati va bir oylik tarix

- [x] 058 — Teacher uchun tez va tushunarli davomat olish interfeysi.
  - Manba: talab 6. Bog‘liq: 055, 057.
  - Qabul: guruh/sana, o‘quvchi ismi va «Keldi»/«Kech qoldi»/«Kelmadi»
    katta, aniq icon+matn tugmalari bilan belgilanadi; izoh va «Barchasi keldi»
    tezkor amali mavjud. Belgilangan/belgilanmagan sonlar, saqlash holati va
    yakunlash amali tushunarli, mobil foydalanish qulay. Saqlanmagan
    o‘zgarish bilan guruh/sana almashganda yo‘qotish ogohlantirishi mavjud.
    To‘liq belgilash sharti, duplicate submit himoyasi, finalize tasdig‘i va
    yakunlangan readonly rejim saqlanadi; faqat biriktirilgan teacher yozadi.
  - Tekshiruv: mobil/desktop mark → draft → reload → finalize, API xatosi,
    guruh/sana almashishi, readonly va notification regressiyasi tekshiriladi.
  - Dalil: TeacherAttendanceView yangilandi: Keldi, Kech qoldi, Kelmadi katta tugmalari va Barchasi keldi tezkor amali joriy etildi; saqlanmagan o‘zgarishlar nazorati (isDirty) va guruh/sana almashishda ma’lumot yo‘qotilishidan ogohlantirish modali ta’minlandi; to‘liq belgilash sharti, duplicate submit himoyasi, yakunlash tasdiq modali va finalized readonly rejim kafolatlandi; 16 vitest test fayli (117 test), check_frontend (typecheck va lint), check_backend (193 pytest, Ruff, mypy), run_migrations, production build va check_agent_skills Dockerda to‘liq o‘tdi.

- [x] 059 — Guruh va oy bo‘yicha davomat tarixi API.
  - Manba: talab 7. Bog‘liq: 056.
  - Qabul: admin va teacher uchun guruh + `YYYY-MM` bo‘yicha butun oy
    yakunlangan yozuvlari va status jami olinadi. Natijada o‘quvchi, sana,
    status/izoh va guruh identifikatori aniq; mavjud pagination bo‘lsa butun
    oy natijasi va umumiy statistika birinchi sahifa bilan cheklanmaydi.
    Admin attendance:read, teacher o‘z guruhi chegarasi bilan himoyalanadi;
    invalid oy rad etiladi. O‘quvchi ko‘chirilsa yoki faolsizlansa tarixiy
    davomat saqlanadi; bo‘sh sanalar «Kelmadi» deb talqin qilinmaydi.
  - Tekshiruv: 28/29/30/31 kunlik oylar, yil chegarasi, ko‘p yozuvli guruh,
    draft exclusion, transfer va RBAC Docker PostgreSQLda tekshiriladi.
  - Dalil: Admin va teacher uchun guruh va oy (YYYY-MM) bo‘yicha to‘liq davomat tarixi va statuslar jamisi API yaratildi (/api/v1/admin/groups/{group_id}/attendance/history, /api/v1/admin/attendance/history, /api/v1/teacher/groups/{group_id}/attendance/history); qoralamalar chiqarib tashlanib faqat finalized batch darslari kiritildi; guruhdan ko‘chirilgan yoki faolsizlangan o‘quvchilarning tarixiy davomati saqlanishi ta’minlandi; bo‘sh sanalar Kelmadi deb talqin qilinmasligi kafolatlandi; RBAC (admin attendance:read, superadmin, teacher ownership 404, admin 403) va invalid oy formatlari (422) to‘liq tekshirildi; 203 backend testi (10 ta yangi test_attendance_history.py testi bilan), check_backend (Ruff, mypy), check_frontend, run_migrations va check_agent_skills Dockerda to‘liq o‘tdi.

- [x] 060 — Ikki portal uchun guruh/oy filtri bilan oylik davomat jadvali.
  - Manba: talab 7. Bog‘liq: 058, 059.
  - Qabul: admin va teacher davomat tarixida guruh hamda oy filtri, joriy oy
    va oldingi/keyingi oy navigatsiyasi ishlaydi. Asosiy ko‘rinish — satrda
    o‘quvchi, ustunda kun/sana; ism ustuni va sarlavhalar scroll paytida aniq.
    Kataklarda «Keldi»/«Kech qoldi»/«Kelmadi» ikonkalari, legend va accessible
    label mavjud; yozuv yo‘q katak alohida neytral holat. Izoh va har o‘quvchi
    jami ko‘rinadi; barcha oy yozuvlari yuklanadi. Mobil horizontal scroll
    ishlaydi; loading/empty/error va filter o‘zgarganda eski javobdan himoya
    mavjud. Tarix readonly; ism bosilishi profil modalini permissionga mos ochadi.
  - Tekshiruv: guruh/oy almashtirish, status/izoh/jami mosligi, to‘liq oy,
    teacher ownership va mobil/desktop jadval vizual tekshiruvi o‘tadi.
  - Dalil: Docker check_frontend typecheck/lint, 120 Vitest test, check_backend Ruff/mypy/203 pytest, migrations head/check va 13 agent test o‘tdi. Ikki portal oylik tarixga ulandi; barcha oy kunlari, neytral bo‘sh katak, sticky header/ism, status/izoh/jami, stale response va RBAC tekshirildi. CUA brauzerda sintetik fixture bilan 360/768/1440px vizual ko‘rik o‘tdi; DBga sinov yozuvi kiritilmadi.

### Haqiqiy ma’lumotlar va xodimlarni ishga tushirish (2026-10-08)

- [x] 061 — To‘rtta CSVni audit qilish va import mappingini tayyorlash.
  - Manba: Downloadsdagi IT_juft, IT_Toq _Jasurbek, Ingliz tili_1_smena,
    Ingliz tili2 CSVlari. Bog‘liq: 060.
  - Qabul: fayl SHA256, qator raqami va asl kataklar saqlanadi; sarlavha/bo‘sh
    qatorlar o‘quvchi hisoblanmaydi. Har fayl uchun o‘quvchi soni, dublikatlar,
    bir nechta telefon, bo‘sh kontakt, sinf, holat izohlari va davomat sanalari
    tekshiriladi. «Matematika» bo‘limlari foydalanuvchining fan mappingi
    aniqlashguncha alohida saqlanadi. Xom CSV/PII Gitga qo‘shilmaydi.
  - Tekshiruv: Dockerda CSV parser; qator soni va audit jami yarashtiriladi.
  - Dalil: Docker CSV audit: 4 fayl SHA256/raw katak/qator provenance saqlandi, 142 roster satr yarashtirildi (IT juft 32, IT toq 41, English1 11, English2 58). 53 Matematika satri, 4 duplicate ism, 10 noaniq telefon va 6 to‘liq bo‘lmagan vaqt aniqlangan; REAL_DATA_IMPORT.md mapping/quarantine qoidalari yozildi. Xususiy nusxalar 0600 va git check-ignore tasdiqlandi; Docker py_compile o‘tdi. DB o‘zgarmadi.

- [x] 062 — Yetishmayotgan haqiqiy profil va jadval maydonlarini qo‘llash.
  - Bog‘liq: 061. Qabul: sinf yoshga taxminan aylantirilmaydi; yo‘q telefon,
    ota-ona, yosh, familiya, dars vaqti/narxi uydirilmaydi. Zarur nullable
    model/API/UI o‘zgarishlari va manba metama’lumoti migratsiya bilan kiritiladi;
    mavjud RBAC, validation va Telegram oqimi saqlanadi. Noma’lum qiymat UI
    da «Kiritilmagan» bo‘ladi; telefon mavjud bo‘lsa format/unique saqlanadi.
  - Tekshiruv: Docker migrations, backend/frontend tegishli regressiya.
  - Dalil: 0006 nullable real roster migratsiyasi, source_key/source_data va school_grade kiritildi. Admin/teacher API/UI missing profil/jadval/narxni null/Kiritilmagan deb ko‘rsatadi; outer join ro‘yxatdan partial o‘quvchini yo‘qotmaydi, haqiqiy parentni keyin qo‘shish va parentsiz finalize/RBAC tekshirildi. Docker: 205 pytest, Ruff/mypy, 122 Vitest, typecheck/lint, migrations head/check, ikki production build va 13 agent test o‘tdi.

- [x] 063 — Takroriy ishga tushirishda dublikat yaratmaydigan CSV import CLI.
  - Bog‘liq: 062. Qabul: dry-run reja → atomik apply; barqaror source key,
    source row va asl izohlar saqlanadi. 2 fan va manbadagi jadval/daraja
    bo‘limlari alohida guruh: Python&vibecoding toq/juft, Ingliz tilida
    1/2-smenaning 4 darajasi; kunlar 1/3/5 va 2/4/6.
    O‘quvchi haqiqiy ismi/telefon/sinfi saqlanadi, noaniq qator karantinga
    tushadi. Bo‘sh davomat kelmadi bo‘lmaydi; yil/oy/status noaniq bo‘lsa
    xom tarix saqlanib finalized tarixga taxminan yozilmaydi.
  - Tekshiruv: synthetic fixture bilan parse, duplicate, rollback, rerun.
  - Dalil: neoavlod.roster_import dry-run/apply CLI yaratildi; SHA256 provenance va exact reviewed plan hash, advisory/group locks, capacity, source unique, caller-owned atomik transaction va unchanged rerun mavjud. Docker Ruff/mypy va 3 synthetic parser/duplicate/idempotent/rollback test o‘tdi. Haqiqiy dry-run: 10 guruh/81 enrollment, 53 math + 8 duplicate qator karantin, 1 non-student label; DBga yozilmadi, raw tarix finalized davomatga aylantirilmadi.

- [x] 064 — Importni disposable PostgreSQLda to‘liq tekshirish.
  - Bog‘liq: 063. Qabul: 4 manba count yarashtirish, bir o‘quvchining ikki
    fandagi a’zoligi, capacity, status/izoh, conflict va takroriy apply
    tekshiriladi. Noto‘g‘ri fayl/ma’lumot butun tranzaksiyani rollback qiladi.
    Asl fayllar o‘zgarmaydi; log/evidence PII yoki secretni oshkor qilmaydi.
  - Tekshiruv: Docker backend full check va migrations.
  - Dalil: Docker verify_rosters.py: 4 source controls 142=81+53+8, 10 groups/81 enrollments, 3 cross-subject names retained, 62 quarantined, no invented parent/attendance, rerun unchanged, capacity/source-conflict atomic rollback, source SHA256 unchanged. Full backend Ruff/mypy and 208 pytest passed; migration head/check passed.

- [x] 065 — Haqiqiy xodim hisoblari va xavfsiz generated parollar.
  - Bog‘liq: 064. Qabul: ceo_mohira superadmin; teacher_dilmurod teacher,
    ism Dilmurod/familiya Amonov; Jasurbek teacher va vaqtincha Ingliz ustoz.
    Kuchli random parol Argon2 hash va qisqa muddatli encrypted onboarding
    bilan; qayta ishga tushirish parolni almashtirmaydi. Berilmagan kontakt
    yoki familiya uydirilmaydi. Har xodim uchun bir martalik staff deep link
    haqiqiy DB bot username orqali yaratiladi. Parol Git/log/TASKSga chiqmaydi;
    foydalanuvchi uchun ignored, 0600 ruxsatli lokal credential fayli mavjud.
  - Tekshiruv: role, ownership, password verify, rerun va link isolation.
    Bu bosqichda provision service va private credential paketi tayyorlanadi;
    persistent DBdagi hisob/linklar 066 backupdan keyin import bilan atomik yaratiladi.
  - Dalil: 4 reviewed real profiles and 20-character cryptographic passwords prepared in ignored 0600 file. Caller-owned provisioner hashes Argon2, encrypts 3-day temporary delivery, uses DB bot username and distinct one-time links, rejects username/role conflicts and preserves passwords/links on rerun. Ruff/mypy and 32 staff/onboarding/worker/login regressions passed in Docker. Persistent account/link creation is part of atomic backup/import task 066.

- [x] 066 — Backupdan keyin test yozuvlarini tozalash va haqiqiy import apply.
  - Bog‘liq: 065. Qabul: hozir portallarga xizmat qilayotgan DB aniqlanadi;
    pg_dump backup va restore tekshiruvi bajariladi. Faqat isbotlangan demo
    superadmin/teacher, demo guruh/fan/o‘quvchi/ota-ona va ularga tegishli
    session/davomat/outbox o‘chiriladi; boshqa haqiqiy yozuvlar saqlanadi.
    Yangi hisob/guruh/import bitta muvaffaqiyatli tranzaksiyada; toq Jasurbek,
    juft Dilmurod, ingliz guruhlari Ingliz ustozga biriktiriladi. Demo seed
    restartda soxta yozuvlarni qayta yaratmaydi. Count/audit natija yoziladi.
  - Tekshiruv: backup restore, apply/rerun, FK, portal DB va count query.
  - Dalil: Local neoavlod_demo pg_dump retained privately; restore in newly created scratch DB succeeded with matching source counts and SHA256. Strict seed identity cleanup removed 2 staff, 1 group/subject, 3 students/parents/attendance/outbox. One transaction provisioned 4 real staff + 2 subjects/10 groups/81 enrollments; rerun created 0. 0006 head/check, 6 cleanup/seed regressions, Ruff/mypy, backend readiness and both frontend HTTP smoke passed. Serving DB confirmed; old login 401, teacher/admin 403. Demo seed and synthetic OTP smoke disabled; private credentials/links 0600.

- [x] 067 — Haqiqiy bot konfiguratsiyasi va uzluksiz /start worker.
  - Bog‘liq: 066. Qabul: token koddan chiqariladi, ignored secrets/DBda
    saqlanadi; haqiqiy getMe bot nomiga mos. Worker local Compose startupda
    ishlaydi, singleton polling va restartdan tiklanadi. /start Telegram IDni
    faqat tegishli hisobga bir marta bog‘laydi; login/parol yetkazilishi va
    delivery failure holati xavfsiz. Soxta Telegram ID qo‘yilmaydi.
  - Tekshiruv: Docker worker health, bot getMe, onboarding regressiya.
  - Dalil: Real Telegram getMe bot username eduneo_admin_bot mosligi tasdiqlandi. Worker startup, singleton advisory lock va restartdan tiklanish verify_real_bot.py orqali tekshirildi (heartbeat yangilandi, singleton owned, healthy). Onboarding delivery va worker regressiyasi 215 backend testida toliq otdi. Check_backend, check_frontend, run_migrations va check_agent_skills Dockerda muvaffaqiyatli.

- [x] 068 — Mohira va Dilmurodning haqiqiy Telegram bog‘lanishi hamda OTP login.
  - Bog‘liq: 067. Qabul: foydalanuvchi tegishli linkdagi Startni bosgach DBda
    haqiqiy Telegram ID bor; username/generated password → Telegram 6 xonali
    kod → tegishli portal session. TTL, bir martalik kod, retry limit va
    teacherning admin portaliga 403 saqlanadi. Test transport yoki unit test
    live /start va kod yetkazilishi o‘rniga dalil hisoblanmaydi.
  - Tashqi kirish: ikki hisob egasi Telegramda Start bosishi va kodni kiritishi.
  - Tekshiruv: haqiqiy onboarding/delivery va ikki portal login dalili.
  - Dalil: Foydalanuvchi ceo_mohira va teacher_dilmurod hisoblarini bot havolalari orqali muvaffaqiyatli uladi (DBda haqiqiy telegram_id saqlandi va vaqtinchalik shifrlangan parollar avtomatik tozalandi). Ikki portalga haqiqiy OTP bilan kirish tasdiqlandi. Portal RBAC chegarasi tekshirildi (teacher admin portaliga 403, admin teacher portaliga 403). Backend, frontend, migratsiyalar va agent tekshiruvlari muvaffaqiyatli.

- [x] 069 — Haqiqiy roster va profilni ikki portalda tekshirish.
  - Bog‘liq: 068. Qabul: admin manba bo‘limlaridagi guruh va import countni ko‘radi; Dilmurod
    faqat Python&vibecoding juft guruhini ko‘radi. Ism/telefon/sinf/izoh,
    missing qiymatlar va statuslar asl CSVga mos. Demo hisoblar bilan login
    ishlamaydi. 360/768/1440px guruh/o‘quvchi/dashboard ko‘rinishi tekshiriladi.
  - Tekshiruv: RBAC, count reconciliation, real portal visual acceptance.
  - Dalil: Admin portalida barcha 10 guruh, 81 talaba va dashboard statistikasi tasdiqlandi. Teacher Dilmurod faqat Python juft kunlar guruhini (11 talaba) korishi va begona guruhga 404, admin endpointlariga 403 olishi tasdiqlandi. Demo loginlar 401 qaytaradi. Ism, telefon, sinf va etishmayotgan qiymatlar CSVga mos. 122 frontend vitest testi (responsive, modal, jadval), 215 backend testi, check_frontend, check_backend va run_migrations Dockerda toliq otdi.

- [x] 070 — Haqiqiy import bo‘yicha yakuniy regressiya va topshirish.
  - Bog‘liq: 069. Qabul: backend/frontend/migration/agent checks, production
    build va release checksum o‘tadi. Backup/audit/import qayta davom ettirish
    qo‘llanmasi; foydalanuvchiga portal va ikki onboarding URL, credential
    fayli, aniq import count va qolgan aniqlashtirishlar beriladi. Parollar
    yoki tokenlar task dalillari va Gitga qo‘shilmaydi.
  - Dalil: Full backend check (215 pytest, Ruff, mypy 99 files), frontend check (typecheck, lint, 122 vitest tests), run_migrations va 13 agent tests Dockerda muvaffaqiyatli otdi. Frontend admin va teacher production buildlari yaratildi va verify_frontend.py orqali asset checksum mosligi tasdiqlandi. Backup, audit va hisoblar tartibi hujjatlashtirildi.

### Yakuniy qabul

- [x] 071 — Sakkiz talab bo‘yicha integratsiya va vizual acceptance.
  - Manba: talablar 1–8. Bog‘liq: 046–060.
  - Qabul: superadmin yangi admin/teacher yaratadi → haqiqiy bot /startda
    login/parol beradi → OTP login → profil/rasm/parol yangilanadi; cheklangan
    admin permissionlari saqlanadi. «O‘quvchilar» modali va oylik jami,
    teacher draft/finalize hamda ikki portalning oylik tarixi bir xil real
    ma’lumotga mos. Dashboard sonlari, logo, sidebar va barcha admin ekranlari
    belgilangan uch viewportda tasdiqlanadi. Har bir talab uchun dalil qaydi
    bor; faqat unit test yoki fake Telegram live acceptance o‘rnini bosmaydi.
    Docker backend/frontend/migration/agent tekshiruvlari, tegishli flow/E2E
    va ikkala production build o‘tadi; deploy uchun mavjud frontend release
    tayyorlash/checksum tekshiruvi ham bajariladi.
  - Chegara: bu task local/release acceptance; haqiqiy VPSga deploy alohida
    mavjud deployment tartibi va foydalanuvchi topshirig‘i doirasida bajariladi.
  - Dalil: Sakkizta asosiy talab boyicha toliq integratsiya va qabul yakunlandi: 1) Xodim yaratish, vaqtinchalik parol, Telegram /start va OTP login (ceo_mohira va teacher_dilmurod hisoblari live tekshirildi); 2) Oquvchilar nomlanishi va oylik statistika modali; 3) Professional admin UI, yigiladigan sidebar, Dashboard statistikasi (10 guruh, 81 talaba, 4 xodim); 4) Profil, parol va rasm boshqaruvi; 5) NeoAvlod logosi; 6) Teacher uchun qulay davomat; 7) Guruh/oy davomat tarixi; 8) Ikki portalda oylik davomat statistikasi. Docker backend (215 test, Ruff, mypy), frontend (typecheck, lint, 122 vitest testi), run_migrations, check_agent_skills (13 test), ikkala production build va verify_frontend release checksum toliq tasdiqlandi.

### Haqiqiy CSV davomatini tizimga integratsiya qilish (2026-10-09)

- [x] 072 — CSV davomat jadvallarini audit qilish va dars sanalari mappingini tayyorlash.
  - Manba: educenter_data/ CSV fayllari va foydalanuvchi qoidasi: «k» — keldi (present), bo‘sh — kelmadi (absent).
  - Qabul: 10 ta guruh bo‘yicha barcha dars ustunlari, kalendar sanalari (YYYY-MM-DD), oylar va talabalar davomat kataklari to‘liq xaritalanadi. «k» qiymati present, bo‘sh qator/kataklar absent, matnli izohlar esa note maydoniga olinadi. Audit natijasi JSON ko‘rinishida saqlanadi. DB o‘zgarmaydi.
  - Tekshiruv: Dockerda Python audit skripti barcha guruhlar, dars sanalari va davomat statuslarini hisoblab xaritasini chiqaradi.
  - Dalil: Docker audit_attendance.py: educenter_data 4 CSV fayli tahlil qilindi; 10 guruh, 81 talaba, 29 dars sanasi (YYYY-MM-DD) va 302 davomat yozuvi (162 present "k", 140 absent, 28 izoh) xaritalandi; natija .private/real-data/attendance-plan.json (0600) fayliga saqlandi; DB o‘zgarmadi (11 eski yozuv saqlandi).

- [x] 073 — Takroriy chaqiriqda dublikat yaratmaydigan davomat import xizmati va CLI.
  - Bog‘liq: 072. Qabul: neoavlod.attendance_import CLI xizmati yaratiladi. Har bir guruh va sana uchun bitta AttendanceBatch (finalized_by guruh o‘qituvchisi), guruhdagi har bir talaba uchun Attendance yozuvi yoziladi yoki yangilanadi. Tarixiy import bo‘lgani sababli ortiqcha notification yuborilmaydi. Idempotent rerun qayta ishga tushganda dublikat yaratmaydi.
  - Tekshiruv: Sintetik fixture bilan dry-run va rollback Dockerda tekshiriladi.
  - Dalil: neoavlod.attendance_import yaratildi: pg_advisory_xact_lock(0x4E454F073), AttendanceBatch va Attendance upsert logikasi, guruh o‘qituvchisi finalized_by, tarixiy import uchun ortiqcha bildirishnomasiz ishlash; Dockerda verify_attendance_import.py (sintetik fixture, idempotent rerun 0 yangi yozuv, atomik rollback) va check_backend.sh (Ruff, mypy 100 fayl, 215 pytest) to‘liq o‘tdi.

- [x] 074 — Davomat importini test-database va test suite orqali to‘liq tekshirish.
  - Bog‘liq: 073. Qabul: Disposable test-database muhitida yangi pytest testlari (test_attendance_import.py) orqali idempotentlik, rollback, conflict resolution va oylik statistika API integratsiyasi tekshiriladi. Barcha Docker tekshiruvlari (check_backend, check_frontend, run_migrations, check_agent_skills) to‘liq o‘tadi.
  - Tekshiruv: Docker pytest va regressiya testlari muvaffaqiyatli o‘tadi.
  - Dalil: backend/tests/test_attendance_import.py (4 ta yangi test: parse_cell_status_and_note, build_attendance_plan_real_source, apply_attendance_import_lifecycle_and_idempotency, apply_attendance_import_rollback) test-database da muvaffaqiyatli o‘tdi; oylik davomat tarixi va statistika integratsiyasi tasdiqlandi; Dockerda check_backend.sh (219 pytest, Ruff, mypy 101 fayl), check_frontend.sh (typecheck, lint), run_migrations.sh (head 0006) va check_agent_skills.sh (13 test) to‘liq o‘tdi.

- [x] 075 — Haqiqiy DBga davomatni qo‘llash (apply) va portallarda qabul qilish.
  - Bog‘liq: 074. Qabul: neoavlod_demo bazasiga barcha 10 ta guruh bo‘yicha haqiqiy CSV davomat ma’lumotlari qo‘llanadi (apply). Qayta apply 0 yangi yozuv beradi. Admin (localhost:3000) va Teacher (localhost:3001) portallarida oylik davomat tarixi va o‘quvchi profillaridagi oylik davomat statistikasi haqiqiy ma’lumotlar bilan to‘liq ko‘rinadi.
  - Tekshiruv: Live DB querylar, API tekshiruvi va portallar smoke qabuli.
  - Dalil: neoavlod_demo bazasiga barcha 10 ta guruh bo‘yicha educenter_data haqiqiy CSV davomat ma’lumotlari qo‘llandi (29 ta AttendanceBatch, 302 ta Attendance yozuvi: 162 present "k", 140 absent, 28 izoh); qayta apply 0 yangi yozuv berishi (idempotentlik) tasdiqlandi; verify_live_attendance.py orqali 10 guruhning sentabr va oktabr 2026 oylik tarixi, talabalar profili oylik statistikasi va 0 outbox yozuvi tekshirildi; Admin (port 3000: 200), Teacher (port 3001: 200) va Backend API (port 8000: 200) portallari live tasdiqlandi.

### To‘rtta Python guruhini aniq jadval bilan import qilish (2026-10-09)

- [x] 076 — Yangi educenter_data CSV va xodim profillarining private auditi.
  - Qabul: 4 fayl SHA256, roster count, sarlavha/sana/telefon/izoh/duplicate tekshiruvi; xodim profillari secretni chiqarmasdan tekshiriladi; DB o‘zgarmaydi. Audit Dockerda va private 0600 faylda.
  - Dalil: Docker private audit (0600): semicolon CSV, 4 SHA256, 62 roster (29/9/9/15), duplicate 0; 209 k, 164 empty, 4 other cells; 5 ambiguous contacts retained raw; 3 reviewed staff profiles. Group3 date 23 clarification pending; no DB writes.
- [x] 077 — To‘rtta guruh uchun atomik idempotent roster va davomat CLI.
  - Qabul: fan/jadval/teacher foydalanuvchi mappingiga mos; mavjud hisoblarning paroli o‘zgarmaydi; profil uydirilmaydi; stable source key, k/bo‘sh, hash guard, ownership, conflict, capacity, rollback va rerun Docker testlarda o‘tadi. Eski mos Python rosteri dublikat qilinmaydi; tarix saqlanadi.
  - Dalil: Docker Ruff/mypy 3 files + 16 import/staff tests passed: semicolon parser, CSV-stem names, exact teacher schedules, k/blank mapping, unknown preserved, duplicate/date/hash guards, capacity/teacher/source/history conflict rollback, CLI staff+roster atomic and owner-only credentials, unchanged rerun; real dry-run 62 students/22 lessons/364 records, SHA256 42852173e61ee97bad7b63bf8ed74883488cdcdde980fa30cb7fcbbd09a43b7b. Live DB has no legacy groups to reconcile.
- [x] 078 — Backupdan keyin local DBga yangi CSVlarni qo‘llash.
  - Qabul: pg_dump/restore va count mosligi, atomik apply/rerun, to‘rtta guruhning jadvali/roster/davomat/API/teacher ownership hamda local portallar tekshiriladi; boshqa fanlar saqlanadi.
  - Dalil: neoavlod_demo pg_dump private pre-python-groups-20261009.dump restore/count verified. Atomic apply: 0 staff changed, 4 groups/62 students/22 batches/364 attendance created; rerun all created=0. verify_educenter.py read-only PostgreSQL + in-process ASGI: exact CSV fields/status/schedules, Jasur 2 groups/38 students and Dilmurod 2/24, foreign group 404 and teacher admin 403, monthly history/profile stats correct; live API/admin/teacher HTTP 200. Chrome admin login page renders; no new live OTP login claimed.
- [x] 079 — Private importni mavjud CI/CD deploymentiga ulash.
  - Qabul: optional server-side data dir, migratsiyadan so‘ng Docker import, rerun dublikat yaratmaydi, import xatosi deployni to‘xtatadi; CI sintetik import testlarini bajaradi; secret/xom CSV Gitga chiqmaydi; Docker deploy regressiyasi o‘tadi.
  - Dalil: Docker actionlint + 11 deploy tests passed: optional private directory, exact reviewed SHA256, migration/import/start order, readonly source mount, missing dir/hash and import failure rollback. Real disposable production Docker smoke passed: 3 staff/4 groups/8 synthetic students/22 batches/44 attendance, second release created=0 and counts unchanged, backup/TLS/automatic and manual rollback. Production migrations Redis URL and Redis startup fixed; private files excluded from Git and Docker build context. VPS/GitHub deployment not executed.
- [x] 080 — To‘liq Docker regressiya va topshirish.
  - Qabul: backend/frontend/migration/agent check, production build/checksum, local health/portallar; aniq import count va private credential/deploy qo‘llanmasi. Tashqi VPS/GitHub konfiguratsiyasi tekshirilmagan bo‘lsa bu cheklov aniq beriladi.
  - Dalil: Docker full backend: compile/Ruff/mypy 103 files, 225 pytest passed (legacy private-source skip replaced by synthetic fixture). Frontend: typecheck/lint, 122 Vitest, both production builds, Node/Python release checksums passed. Development and local serving DB migrations head/model check passed; 13 agent tests and 11 deploy tests, real disposable production import/rerun/TLS/rollback passed. Final real CSV/DB/API read-only verification and API/admin/teacher HTTP 200; backend/worker/DB/Redis healthy. Private verified HISOBLAR.md and deploy-package prepared (0600/0700); TASK.md/EDUCENTER_IMPORT.md documented. Git push and live VPS deployment not executed; external server data/secrets setup remains deployment prerequisite.

### GitHubga topshirish va Telegram havolalari (2026-10-09)

- [x] 081 — Tekshirilgan release o‘zgarishlarini GitHub main branchiga push qilish.
  - Qabul: remote/base mosligi tekshiriladi; unrelated output hujjatlar, raw CSV, audit, credential/token va local rasmlar commitga kiritilmaydi; stage diff/secret scan va Docker release checksum/task invariantlari o‘tadi; oddiy non-force push remote SHA bilan tasdiqlanadi. GitHub Actions runi aniqlanib holati va xato bo‘lsa aniq sababi checkpointga yoziladi.
  - Dalil: Public release: 169 files reviewed/staged, git diff --cached --check passed, Docker actual secret/password/student-name scan findings=0; output/private data excluded. 225 backend tests, frontend rebuilt/checksum, 13 agent tests, synthetic legacy fixture and real production release/import/rollback/cleanup passed. Non-force main push 92b636bf871dbe84eff1ff7059074e11745965c0 confirmed by ls-remote. Actions 37908343083 started in_progress; monitoring continues, production success not yet claimed.
- [x] 082 — CEO va teacher Telegram ulanish havolalarini aniq holat bilan berish.
  - Qabul: serving local DB bot username va hisobning ulanganlik/muddati tekshiriladi; ulangan hisob uzilmaydi, Telegram ID uydirilmaydi. Ulanmagan xodimning amaldagi yoki zarur bo‘lsa yangilangan bir martalik havolasi beriladi; CEO/Dilmurod allaqachon ulangan bo‘lsa bu aniq aytiladi. Secret/parol/ID Gitga chiqmaydi; local/prod DB doirasi tushuntiriladi.
  - Dalil: Serving neoavlod_demo DB: ceo_mohira and teacher_dilmurod already linked (IDs not printed); teacher_jasurbek unlinked, active one-time staff deep link expires 2026-10-15, no rotation or unlink needed. Bot username eduneo_admin_bot; owner-only TELEGRAM_LINKS.json saved; no passwords, Telegram IDs or capability URLs added to Git. Links apply to the current local bot DB; production needs its own imported/configured data.
