# NeoAvlodLMS — vazifalar va davom ettirish holati

## Ish doirasi va joriy holat

Talablar manbasi: foydalanuvchining 2026-10-05 dagi topshiriqlari. Joriy doira:
Docker muhitini hozir yaratish va qolgan barcha vazifalarni ketma-ket Docker
muhitida bajarish. Kod tahriri hostda mumkin; backend, bot, frontend, test,
lint, typecheck, migratsiya va task-manager Python jarayonlari konteynerda.
Host Python/Node/venv ishlatilmaydi. Oldingi Task 001 hostda tekshirilgan;
Task 002 dan barcha tekshiruvlar Dockerda qayta bajariladi.

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

Faol registry task yo‘q; 001–044 repository vazifalari tekshirilib yakunlangan.
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
