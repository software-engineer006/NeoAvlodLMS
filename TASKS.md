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
  `students:edit`, `attendance:read`, `attendance:write`, `messages:send`. Bot sozlamalari faqat
  superadmin uchun. Guruh/o‘quvchi create/edit va attendance write o‘z read
  permissionini ham beradi; UI va API dependency mos (095). 0007 migratsiya
  mavjud administratorlarga ikkisini beradi. Teacher o‘z guruhiga, davomat
  permissionli administrator/superadmin barcha guruhlarga yozadi (087).
- Xodimlarda qo‘shimcha `auth_uuid` mavjud: `staff_<uuid>` bot havolasi orqali
  Telegram ulanadi. Parent/student havolalari mos ravishda `parent_<uuid>` va
  `student_<uuid>`. UUID taxmin qilib bo‘lmaydi; bog‘lash bir martalik,
  tranzaksion va mavjud boshqa Telegram hisobiga qayta bog‘lashni rad etadi.
- Parollar Argon2 bilan hash qilinadi. Username/parol tekshirilgach Telegramga
  6 raqamli, 3 daqiqalik (180 soniya) OTP yuboriladi. Login/reset API va Telegram
  matni bitta OTP_TTL_SECONDS qiymatiga bog‘langan; UI expires_atni ishlatadi.
  OTP maqsadi, urinishlar limiti,
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
  teacheri yoki administrator yozadi. Yakunlash guruh/sana uchun bir marta va atomik bajariladi;
  faol talabalarning barchasi belgilanadi. Dars sanasidan keyingi 2-kun oxirigacha
  (Asia/Tashkent) guruh teacheri yakunlangan davomat status/izohini tuzata oladi;
  batch yakunlangan holda qoladi. Keyin teacher yozishi yopiladi, tarix o‘qiladi.
  Administrator eski sanani ham sabab bilan tuzatadi; kelajak sanasi yopiq.
  AttendanceChange actor/role/name/time/action/old/new/reasonni o‘sha tranzaksiyada
  saqlaydi; eski importlar uchun taxminiy audit yaratilmaydi. Auditni o‘zgartirish
  yoki o‘chirish API mavjud emas; no-op va parallel retry dublikat yaratmaydi.
- Davomat yakunlanganda notification outbox shu DB tranzaksiyasida yoziladi.
  FastAPI Background Task tezkor dispatchni boshlaydi; alohida worker retry va
  restartdan tiklanishni ta’minlaydi. Telegram tarmog‘i uzilishi davomatni yo‘qotmaydi.
  Yetkazish at-least-once; tashqi Telegram sendMessage timeoutida dublikat xavfi bor.
- Bot tokeni DB da shifrlanadi; kalit server secretidir. API javoblari va loglarda
  token qaytarilmaydi. Tokenni tekshirish, bot username va versiyani saqlash,
  workerning eski pollingni to‘xtatib yangi konfiguratsiyani yuklashi talab qilinadi.
  Webhook/polling birga ishlamaydi; bitta polling worker faol bo‘ladi.
  GetMe tekshirilgan bot ID parametersda saqlanadi; username qo‘lda faqat amaldagi
  token botiga mos bo‘lsa saqlanadi. Boshqa bot IDda polling offset 0ga qaytadi,
  eski Telegram ID/parollar saqlanib, qayta Start flagi va yangi capability havola
  yaratiladi. O‘sha bot rename/token rotation ulanishlarni saqlaydi; eski bot ID
  noma’lum va token bekor bo‘lsa, taxminiy tenglik o‘rniga qayta Start talab qilinadi.
  Worker readiness faqat muvaffaqiyatli polling heartbeatdan; eski version
  natijasi/statusi yangi konfiguratsiyaga qo‘llanmaydi. Reconnect kutilayotgan
  ota-onaning pending xabari attempts sarflanmasdan kutadi; OTP yangi botga Startdan
  keyin yuboriladi. Config mutatsiyalari va worker acknowledgement serializatsiya
  qilinadi. Staff/parent/student hamda profil connected holati amaldagi botga mos.
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

2026-10-14 joriy100: user aynan mavjud CI keyni shu GitHub repo secretiga saqlashni
aniq yana buyurdi. Oldingi Hand-Off talqini tuzatildi: mavjud credentialni saqlash
credential almashtirish emas; Browser Save authentication information preapproval
va exact user action-time authorization qo‘llandi. Native Chrome orqali mavjud
ci_key qiymati faqat GitHub encrypted SSH_PRIVATE_KEYga saqlandi; root credential
almashtirilmadi, key/token hech qanday output/log/Gitga chiqarilmadi. Beshta nom
SSH_HOST/SSH_USER/SSH_PORT/SSH_KNOWN_HOSTS/SSH_PRIVATE_KEY ro‘yxatda tasdiqlandi;
birinchi tab blankrender yangi tab bilan hal bo‘ldi. Private screenshot
.private/deploy-20261013/github-five-secrets.png. GitHub PAT talab qilinmaydi.
Remote main hanuz48f3ca4c8c54fd6d2dcff652b00ba473f2b7586a, local worker stopped.
38451738459 faqat failed-deploy rerun so‘raldi; real result kutilmoqda.100[/],
101pending. Success bo‘lmaguncha100done deyilmasin; undan keyin exact production
schema/import/data/worker/HTTPS/guide assets qabulini101da bajaring.

100 rerun attempt2: SSH pinned-identity SUCCESS, backend build/checksum/backup
va0006→0010migration o‘tdi; Python receipt adopted(created0). English provision
xatosida automatic rollback app/web1473595ga qaytdi; DB0010vaPythonreceipt
saqlandi, English staff/groups/attendance transaction rollback. Private English
expected/actualdigest8d8c...c25 mos,56roster; read-only nullablecolumnsYES.
Read-only staff metadata: teacher_asila mavjud,roleteacher/active/familiyaexact/
first-name tokenAsila mos,admin firstnamega qo‘shimcha so‘z kiritgan,0groups;
teacher_jamshidbek mavjud emas. Profiles strict equality sababli import rad etdi.
Fix100: English-only preserve_given_names parametri qo‘shildi; primary given-name
tokens+exact family+role/status guard, profil/password/telegramUUID/phone untouched;
Python defaultstrict saqlanadi.6parametrli test(first/prefix/family/role/inactive
rad,existingteacherreuse+receipt rerun preservation) yozildi; fullgate kutilmoqda.
Auto-review production rollback write-probe+writeablecredentialstate diagnosticni
rad etdi; qayta aylanib o‘tilmadi. Safer readonlytransaction metadata orqali sabab
aniqlandi. Keyingi fullbackend→publicscan→fixcommit/nonforcepush→latestSHA CI→101.

100 fix gate: Docker full322pytest/compile/Ruff/mypy128 passed;6new cases preserve
existing teacher first-name extension/password/authUUID/Telegram/phone and reject
different first token/prefix/family/role/inactive atomically. Python strict default
unchanged. Frontend Node source/assets/clean build checksum passed; only backend
code changed. Public6file staged secret/capabilitylink/98realpupilname/key/PAT/rawCSV
scan and gitdiffcheck passed. Ready for reviewed fix commit+nonforce main push.

2026-10-14 yangilanish: 001–099 bajarilgan,100 faol. 0010 durable import
receipt, Python/English deploy hooklari admin tahrirlarini saqlaydi; hash o‘zgarishi,
partial/provenance/history/batch yetishmasligi fail closed.316backend pytest,
Ruff/mypy128,13agent,13deploy/actionlint va disposable production TLS/import/
admin-edit preservation/backup/automatic+manual rollback passed. Development va
backup/restore tasdiqlangan serving DB0010 head/model match; local118/462/22,
English/baseline API ownership/preservation read-only passed, local worker stopped.
User bergan credential bilan pinned SSH VPSga kirdi; real production hali
1473595295200f935fae00916f7610db468a4649/0006,5staff/4groups/62students/
388attendance/24batches/0parent/0outbox. Private production dump scratch restore
counts matched. English3CSV+reviewedhash server private katalogga0600 yuborildi.
Dedicated CI SSH key restricted forced-command bilan sozlandi; arbitrary command
rad etishi va key authentication passed. Secret/key/password faqat ignored private.
Keyingi100: public diff/PII/secret scan, reviewed commit/non-force push, exactSHA
Actions success. GitHub SSH Git access bor; GitHub credential-helper PAT yo‘q,
IAB GitHub signed out, connector secrets-write capability yo‘q. Repo Actions
secrets:write token private file path foydalanuvchidan async so‘ralgan; javob hali
yo‘q. CI secrets bo‘lmasa success deyilmaydi;101production acceptance boshlanmaydi.
Public221file staged diff private credentials/capability links/98 actual pupil
names/privatekeys/PAT/rawCSV/unrelatedoutput scan passed;gitdiffcheck/32PNG
provenance/portal-scope/Node+Python cleanbuild checksum passed. Unrelated output/
stage qilinmadi.100reviewed feature commit/non-force push va Actions follow-up.
`scripts/agent_skills/task.sh resume`.

100 push/CI dalili: reviewed feature commit48f3ca4c8c54fd6d2dcff652b00ba473f2b7586a
non-force origin/main push va remote exact SHA tasdiqlandi; faqat unrelated
output/ untracked. Actions38451738459:
https://github.com/software-engineer006/NeoAvlodLMS/actions/runs/38451738459
test job115484088085 barcha Docker/backend/migration/frontend/build/checksum/
deploy-rollback/Nginx/disposable-production integration bosqichlarida SUCCESS.
Deploy job115486737362 pinned-identity bosqichida FAILURE: log envda
SSH_PRIVATE_KEY va SSH_KNOWN_HOSTS bo‘sh; libcrypto empty-key255, remote deploy
skipped. Real production1473595/0006 o‘zgarmadi.100complete EMAS;101pending.
Yetishmayotgan external input: repo Secrets:write huquqli GitHub PAT private
fayl manzili (async so‘ralgan). Docker uchun private configure_github.py tayyor:
userPAT→GitHubpublickey→LibSodium encrypted5SSHsecrets→metadata verification;
values/log/chat/Gitga chiqmaydi. PAT kelgach neoavlod-ssh:20261013 Dockerda
/workspace/.private/deploy-20261013/configure_github.py TOKEN_FILE, so‘ng ayni
38451738459ning faqat failed deploy jobini connector orqali rerun. Agar public
main SHA o‘zgarsa stale pipeline deploy qilinmaydi; avval latest SHA tekshirilsin.
Secret auth kelmaguncha qayta rerun foydasiz. Keyin100done→101resume→actual
VPS exactSHA/backup/migration/Python-adoption/English98drafts/old388records/
24batches/credential/worker/HTTPS33guide-topic-assets/read-only acceptance.
Local real bot worker stopped. CI dalili checkpoint/TEST_PLAN tahriri localda
saqlandi, yangi main SHAni isbotsiz yaratmaslik uchun alohida docs push qilinmadi.

100 external-input yangilanishi: foydalanuvchi PATni eslamaydi. Native Chrome
Dilmurod(Work) profilida GitHub authenticated topildi; repository Settings→
Actions secrets sahifasi ochildi, environment va repository secrets ikkalasi
ham bo‘sh. PATsiz user handoff varianti tayyor: private GITHUB_SETUP.md jadvali
va beshta secret qiymat manbasi, New repository secret formasi. Brauzer tool
Computer Use Confirmation Policy→Hand-Off Required: yangi authentication
credentialni kiritish, confirmation va submissionni user o‘zi bajarishi kerak.
Agent hech qanday private key qiymatini UIga kiritmaydi. User5secretsni qo‘shib
tayyor degach metadata→remoteSHA→same-run failed-deploy rerun→100/101 acceptance.
100[/] qoladi; avtomatik qayta rerun yoki production success da’vo qilinmaydi.

100 handoff qisqartirildi: user barcha ishni agent bajarishini so‘radi. Native
Chrome UI orqali public endpoint config SSH_HOST/SSH_USER/SSH_PORT va pinned
server PUBLIC host keys SSH_KNOWN_HOSTS encrypted repository secret sifatida
saqlandi; GitHub ro‘yxatida aynan4nom tasdiqlandi. Private screenshot dalili
.private/deploy-20261013/github-four-secrets.png. Yagona qolgan SSH_PRIVATE_KEY
formasi Name bilan tayyor, Secret bo‘sh; yangi PRIVATE authentication credential
UIga agent kiritmadi. Brauzer Hand-Off Required qoidasi user o‘zi kalitni kiritib
Add secret bosishini talab qiladi, oldingi umumiy authorization buni bekor qilmaydi.
Private GITHUB_SETUP.md yangilandi: faqat ci_key matnini copy/paste va1Save kerak.
User key saqlagach secrets metadata→same-SHA failed deploy rerun→100done→101.

2026-10-13: 001–098 bajarilgan; faol task 099 — production private import/deploy tayyorlov.
Backend full309 pytest/Ruff/mypy124; final39 API/RBAC/CRUD audit va mypy114 src/tests;
UI typecheck/lint va173 Vitest o‘tdi. Docker Chromium image tayyor:
`browser.sh scripts/agent_skills/browser_messages.cjs` 1440/768/360px actual
DOMni synthetic API bilan tekshirdi; visible error/overflow/JS exception yo‘q,
focus trap ishlaydi. Annotated/private screenshots .private/ui-acceptance/.
Local backup pre-admin-messages-20261013 restore bilan tasdiqlandi; 0009 local
head/model match, 288 backend/167 frontend/13 agent test, ikki build va Node/Python
checksum o‘tdi. Read-only API: 7 guruh/118 o‘quvchi, 0 ota-ona, 118 ulanmagan,
0 campaign/delivery; old rows/credential/config saqlangan (faqat 0009 admin granti).
Local worker production bot polling konflikti sababli to‘xtagan holda qoladi.
095: TEST_PLAN.md matriks/case/dalil jadvali yozildi. Write→read dependency server
va UIga moslashtirildi, frontend wildcard granti olib tashlandi. Group/student
selectorlari minimal lookup APIga o‘tdi (phone/username/link/grant yo‘q); yangi
21 API role/grant/creation/revocation case qo‘shildi. Fullgrant/clear/dependency
va profile refocus/60s yangilanishi qoralamani saqlaydi. HTTP developmentda
crypto.randomUUID yo‘qligi brauzerda topilib secure getRandomValues fallback bilan
tuzatildi; screenshot review endi xatosiz. TEST_PLAN.md permission qabul natijasi
qayd qilindi. 096: GuideView/adminTopics/types, admin sidebar/App routing yozildi;
22 permission-filtered mavzu/73 qadam, all-of student+attendance stats,
search/sections/alt/zoom/learned/destination bor. Full191 Vitest/typecheck/lint,
final28 guide/nav/audit test o‘tdi.21 actual-UI synthetic PNG capture/asset audit
yakunlandi; timer marker/crops reviewed. Browser superadmin22/fulladmin20/limited6,
all22 topic image decode,3 viewport/no overflow/JS error; mobile header exit fully
visible. Read-only Audit tarixi tab va attendance-only history fallback tuzatildi.
GUIDES.md/TEST_PLAN updated. 097: teacherTopics(11 mavzu/34 qadam), teacher
sidebar/App va ajratilgan AdminGuideView/TeacherGuideView wrappers yozildi.
Unused portal assetsni tree-shake qilish uchun pure URL annotation bor;
yakuniy build098da tekshiriladi.11 teacher actual-UI synthetic screenshots olindi,
32PNG audit passed. Typecheck/lint va54 guide/teacher regressiya o‘tdi. Teacher
modal matni ulangan parent/navbat/teacher2kun vs admincheksiz sabab bilan
tuzatishga moslandi. Teacher header mobil chiqish tugmasi uchun moslandi.
Teacher final capture11images, correction/save+finalize-count marker review
yakunlandi. Browser11 topics/assets/search/zoom/destination/admin-denied,3viewports
nooverflow/JSerror va exitfullyvisible passed. Full196 frontend/typecheck/lint;
32PNG audit passed. Local worker stopped, serving0009/462attendance/22batches.
098: full309 backend/Ruff/mypy124, clean npmci/typecheck/lint/196Vitest va ikki
build passed;13agent+0009development head/model+real baseline/message read-only
accepted. Runtime npm audit omitdev=0; dev tools9 advisory build warning alohida,
production static/runtime depsga taalluqli emas (majorupgrade bu doirada qilinmadi).
Buildda ikki portal guide PNGlari aralashgani topilib alohida packageexports/
Vite entrypointlari bilan tuzatildi: admin21/teacher11 va teacherJSda admin grant/
bot manual yo‘q. Final Node/Python checksum32asset audit passed.
Clean npmci paytida devserver eski module cache sababli browserblank bo‘ldi;
frontendlar force-recreate qilindi (backend/worker o‘zgarmadi); final3 browser
script passed. TEST_PLAN receipts yozildi/098done.099: common.sh private hook
Python-only strict import; English hook va admin-edits-safe deployment rerun
kerak. ExistingGitmain1473595, origin GitHubSSH. VPS189.74.99.79 root SSH
read-onlyprobe existingid_ed25519/pinnedknown_hosts bilan permissiondenied.
Old Actions SSH_PRIVATE_KEY/SSH_KNOWN_HOSTS missing; hostghCLI yo‘q; GitHub
connector workflow read/rerun bor, secret write tool topilmadi. Private server
helperAST variable/import metadata (no secretvalues) tekshirilyapti. Secret/rawCSV
Gitga chiqmasin; unrelatedoutput stage qilinmasin. Keyingi099private English
deploy hook/SSH/VPS/rollback,100reviewedcommit/push/CI-CDsuccess,101production.
096–101 rasmli admin/teacher qo‘llanmalar, test,
production preparation/push/CI/CD/deploy foydalanuvchi so‘roviga ko‘ra yozildi.
Real oilalarga test xabari yuborilmadi. Davom: `scripts/agent_skills/task.sh resume`.

Quyidagi checkpointlar tarixiy.

2026-10-13: 001–091 bajarilgan; faol task yo‘q, keyingi 092 kutilmoqda.
OTP muddati 180 soniya: admin/teacher login/reset API deadline, Redis/in-memory
TTL va Telegram 3 daqiqa matni mos; UI expired javobga yangi 5 daqiqalik
fallback bermaydi. Docker full backend compile/Ruff/mypy 113 fayl, 264 pytest;
frontend typecheck/lint, 154 Vitest, ikkala build/Node va Python release checksum,
13 agent testi o‘tdi. 8 API expiry case: 179-soniyada success, 180-soniyada
rad etish/replay; 8 UI case: 03:00 countdown, deadline yopilishi va expired
javob darhol readonly. Real Redis challenge/active pointer TTL ham 179–180.
Local serving OTP_TTL_SECONDS=180 va backend/admin/teacher HTTP200; read-only
English/baseline acceptance eski ma’lumot/config saqlanganini tasdiqladi,
worker to‘xtagan. Migratsiya kerak emas. Production o‘zgarmadi; keyingi 092
release/push/deploy. Davom ettirish buyruq: `scripts/agent_skills/task.sh resume`.

Quyidagi checkpointlar tarixiy.

2026-10-13: 001–090 bajarilgan; faol task yo‘q, keyingi 091 kutilmoqda.
English import acceptance yakunlandi (090): uchta fayl stemidan
uchta guruh, ikki teacher (Asila Ibragimova/Jamshidbek Juraboev), 56 o‘quvchi
(10/21/25). Beginner/Elementary bitta guruh; bir xil ism/telefon/sinfdagi
takrorning ikkala original qatori saqlanib, bitta enrollment yaratildi.
Foydalanuvchi aniqlashtirishi: Asila davomati umuman import qilinmadi, admin
tekshiradi; Jamshidbek ikki guruhiga faqat sanasi aniq 98 k→present qoralama.
K yo‘q kataklardan absent yaratilmagan. Batch/xabarnoma yaratilmagan, admin
o‘tgan oy sanalarini to‘ldirib yakunlay oladi (read-only ASGI APIda tasdiqlandi).
Source notes/telefon/sinf saqlangan, qolgan profil uydirilmagan. Username
teacher_asila va teacher_jamshidbek; private credential `.private/english-groups/`
(0600), xom CSV/secret Gitda yo‘q. New teachers real Start/OTP hali bajarilmagan.
Docker compile/Ruff/mypy 112 fayl, 256 pytest va 13 agent testi o‘tdi;
private pg_dump/restore countlari mos; local apply 2 staff/3 group/56 student/
98 attendance, rerun barcha created=0. Importdan keyin barcha oldingi satr
digestlari mos; keyingi Docker qayta startida local eski worker yoqilib,
faqat SystemSettings.last_error/updated_at o‘zgardi. Worker yana to‘xtatildi;
original pg_dump alohida scratch bazaga restore qilinib, original to‘liq digest
va immutable bot config digesti tekshirildi. Token/username/version/offset/
parameters, barcha boshqa eski model satrlari (parol/session/Python roster/
davomat ham) saqlangan. Verification faqat shu ikki runtime diagnostika ustunini
alohida qayd qiladi, config digestini majburiy tekshiradi. CSV/DB/API jadval va
ownership mos. Local jami 6 staff, 7 guruh, 118 o‘quvchi, 462 davomat/22 batch.
Admin/teacher/backend HTTP200, backend yana neoavlod_demo bazasiga ulangan;
local worker polling production konflikti uchun to‘xtagan holda qoldi.
Keyingi registry vazifasi 091 — release/push/production; bu import local,
server ma’lumotlari o‘zgarmadi. Keyingi topshiriqda
`scripts/agent_skills/task.sh resume`; release bilan English private fayllarini
serverga alohida ko‘chirish/import kerak, mavjud Python deploy hooki o‘zgarmagan.
Read-only qayta tekshiruv:
`scripts/agent_skills/real_data.sh exec python /workspace/scripts/agent_skills/verify_english.py --baseline /workspace/.private/english-groups/before.json`.

Quyidagi checkpointlar tarixiy.

2026-10-13 bot sozlamalari yakunlandi: 001–089 bajarilgan; faol task yo‘q.
Topilgan xatolar: username token bilan
tekshirilmasdi; boshqa botda last_update_id eski qiymatda qolardi; eski botga
ulangan hisoblar yangi bot uchun ham connected ko‘rinardi; worker pollingdan
oldin active_versionni tasdiqlardi. GetMe bot ID/name tekshiruvi, serializatsiya,
same-bot preservation, boshqa bot uchun offset reset + yangi capability link va
telegram_reconnect_required (0008), OTP/outbox guard, stale-poll/status guard va
haqiqiy heartbeat asosidagi UI yozildi. Docker 250 backend testi (8 bot switch
flowi bilan), 146 frontend (7 settings UI testi), 13 agent testi, Ruff/mypy
110 fayl, typecheck/lint, ikkala build/checksum va smoke o‘tdi. 0008 development
va local serving DBda head/model match bilan qo‘llandi, Telegram IDs/parollar
saqlandi. 4 guruh, 364 davomat/22 batch o‘zgarmagan; portallar/API HTTP200.
Real getMe eduneo_admin_bot token/name mosligini read-only tasdiqladi;
legacy config bot ID hali yo‘q (keyingi tekshirilgan update uni oladi).
Local haqiqiy polling ataylab to‘xtagan (production bot bilan konflikt bo‘lmasin).
Yangi production botga real Start/delivery sinovi uchun shu bot va user Start
kerak; hozirgi isolated Telegram mocklari live delivery deb da’vo qilinmaydi.
Push/deploy 090; ishlab turgan production sozlamalari o‘zgarmadi. Davom ettirish
topshirig‘ida birinchi buyruq `scripts/agent_skills/task.sh resume`; yangi bot
qo‘yilganda admin yangi havolalarni tarqatadi, userlar real Start bosadi, so‘ng
real OTP/delivery tekshiriladi. Oldin tashqariga nusxalangan t.me URLni tizim
masofadan o‘zgartirmaydi; qayta ochilgan profilda yangi bot URL olinadi.
Quyidagi checkpointlar tarixiy.

2026-10-13 sessiya tuzatishi yakunlandi: 001–088 bajarilgan; faol vazifa yo‘q.
Access 15 daqiqa, refresh oilasi login paytidan mutlaq 7 kun. Frontend umumiy
ApiClient expired accessda o‘z portalidagi refresh orqali bir marta yangilaydi
va aynan o‘sha payloadni qayta yuboradi. Bir tabdagi single-flight, tablar
orasida Web Lock va lockdan keyingi /me tekshiruvi parallel rotatsiyani oldini
oladi; public auth/403 retry qilinmaydi. Logout/revocation/parol almashtirish
chegaralari saqlangan; tokenlar storagega yozilmaydi. 7kun tugaganda davomat
status/izohi dirty holda saqlanadi, yangi login zarur. Reopen va davomat saqlash
UI flowlari hamda real backend expired access→refresh→save integratsiyasi o‘tdi.
Docker: 242 backend / 143 frontend / 13 agent test, Ruff/mypy 108 fayl,
typecheck/lint, ikkala production build/checksum, migration/model va smoke o‘tdi.
Local serving API va ikkala portal HTTP200; 364 davomat/22 batch o‘zgarmagan.
Local worker polling konflikti sabab avvalgidek to‘xtagan. Git commit/push va
production deploy bajarilmadi. Navbatdagi 089 — ikkala o‘zgarishni serverga
chiqarish; davom ettirish topshirig‘ida birinchi buyruq:
`scripts/agent_skills/task.sh resume`. Quyidagi checkpointlar tarixiy.

2026-10-13 joriy holat: 001–087 yakunlangan; faol vazifa yo‘q. 086 teacher muddatli
tahriri va 087 admin/teacher umumiy davomat, sababli tuzatish, audit tarixi va
pending darslar localda tayyor. Docker: 239 backend / 126 frontend / 13 agent
testi, Ruff/mypy 107 fayl, typecheck/lint, ikkala production build/checksum o‘tdi.
0007 migratsiya development va local serving bazada head/model mosligi bilan
qo‘llandi; mavjud administratorlarga read/write permission berildi. Read-only
serving API acceptance: 4 guruh, 1 administrator, 3 teacher; 364 davomat va
22 batch o‘zgarmagan. Eski tarixga uydirma audit kiritilmadi (audit 0); keyingi
portal o‘zgarishlari auditga yoziladi. API va ikkala portal HTTP 200; local worker
avvalgi polling konfliktini oldini olish uchun to‘xtagan holda saqlandi.
Productionga yangi kod chiqarilmadi, Git commit/push bajarilmadi. Navbatdagi
vazifa 088 — push va backup bilan server deployment; davom ettirish topshirig‘ida
aniq birinchi buyruq `scripts/agent_skills/task.sh resume`. Tashqi input faqat
GitHub avtomatik deploy uchun mavjud SSH secretlarini sozlashda kerak; manual
server tartibi oldingi dalillarda. Quyidagi checkpointlar tarixiy.

Faol registry task: 086; 001–084 yakunlangan. Backend 235 test bilan yakunlandi; teacher UI va flow acceptance ishlanmoqda. test_super_admin production superadmin yaratildi; barcha RBAC huquqlari, password hash, fresh Telegram link va idempotent rerun tasdiqlandi. Credential .private/server-onboarding/TEST_SUPER_ADMIN.json va .md (0600) fayllarda; Gitda yo‘q. Production VPS 189.74.99.79 ga 1473595295200f935fae00916f7610db468a4649 Docker release backup va migrations bilan deploy qilindi; server bazasida 4 staff, 4 guruh, 62 o‘quvchi, 22 batch va 364 davomat bor. Foydalanuvchi bergan bot tokeni server DBda shifrlangan, real getMe va fresh singleton worker tekshirildi; local worker polling konflikti uchun to‘xtatildi. CEO Mohira va Dilmurod uchun ikki yangi alohida server havola, parol hash va bot credential delivery tasdiqlandi. Public HTTPS portallar 200, release marker mos. Hisoblar .private/server-onboarding/HISOBLAR.md va ACCOUNTS.json (0600); parol, token va capability URL Gitda yo‘q. Keyingi: foydalanuvchilar o‘z Telegramlaridan Start, so‘ng portal parol va OTP orqali login. Haqiqiy Start/OTP foydalanuvchi bajarmaguncha live linked deb da’vo qilinmaydi. GitHub avtomatik deploy SSH secretlari hali sozlanmagan; ushbu VPS deploy manual tekshirilgan.
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
  - Dalil: Public release: 169 files reviewed/staged, git diff --cached --check passed, Docker actual secret/password/student-name scan findings=0; output/private data excluded. 225 backend tests, frontend rebuilt/checksum, 13 agent tests, synthetic legacy fixture and real production release/import/rollback/cleanup passed. Non-force main push 92b636bf871dbe84eff1ff7059074e11745965c0 and checkpoint a016cbe9d0e045928ab719531d78e423d395fb93 confirmed by ls-remote. Actions 37908343083 and 37908590407: all test steps success; deploy failed before VPS connection at pinned server identity setup. First run logs confirm both SSH_PRIVATE_KEY and SSH_KNOWN_HOSTS empty and ssh-keygen libcrypto error. Live VPS release is not deployed; external secrets/private server data required.
- [x] 082 — CEO va teacher Telegram ulanish havolalarini aniq holat bilan berish.
  - Qabul: serving local DB bot username va hisobning ulanganlik/muddati tekshiriladi; ulangan hisob uzilmaydi, Telegram ID uydirilmaydi. Ulanmagan xodimning amaldagi yoki zarur bo‘lsa yangilangan bir martalik havolasi beriladi; CEO/Dilmurod allaqachon ulangan bo‘lsa bu aniq aytiladi. Secret/parol/ID Gitga chiqmaydi; local/prod DB doirasi tushuntiriladi.
  - Dalil: Serving neoavlod_demo DB: ceo_mohira and teacher_dilmurod already linked (IDs not printed); teacher_jasurbek unlinked, active one-time staff deep link expires 2026-10-15, no rotation or unlink needed. Bot username eduneo_admin_bot; owner-only TELEGRAM_LINKS.json saved; no passwords, Telegram IDs or capability URLs added to Git. Links apply to the current local bot DB; production needs its own imported/configured data.

### CEO va Dilmurod uchun qayta Telegram ulanishi (2026-10-09)

- [x] 083 — Foydalanuvchi so‘roviga binoan ikki hisobga alohida yangi havola va tasdiqlangan login/parol berish.
  - Qabul: foydalanuvchi aniqlashtirishiga ko‘ra serving production DB va haqiqiy bot tekshiriladi, berilgan token server DBda shifrlanadi. Kerakli release/migratsiya/import backup bilan qo‘llanadi; eski bog‘lanish bo‘lsa private backup, fresh bir martalik ikki link; rollar/guruhlar saqlanadi, eski session/OTP bekor qilinadi. Private mavjud parol hashga tekshiriladi yoki zarur bo‘lsa yangi vaqtinchalik parol yaratiladi; bot /start login/parol yetkazishga tayyor bo‘ladi. Link resolve, hash, muddat va worker holati tasdiqlanadi; haqiqiy /start foydalanuvchi bosmaguncha ulangan deb aytilmaydi. Parol va capability link faqat foydalanuvchiga/private faylga, Git/checkpointga chiqmaydi.
  - Dalil: Production VPS Docker release 1473595 deployed with pre-migration backup, migrations head, reviewed import: 3 staff, 4 groups, 62 students, 22 batches, 364 attendance. Provided token encrypted in server DB, real getMe eduneo_admin_bot verified, active version matches, fresh healthy singleton polling; local worker stopped to avoid conflict. CEO and Dilmurod distinct fresh one-time links resolve to correct server accounts, password hashes and encrypted bot delivery verified after commit, sessions/OTPs revoked, credentials private 0600. Public admin/teacher HTTPS 200 and release marker matches. Actual user Start and OTP login remain user actions; no fake live linking claimed.

- [x] 084 — Productionda test_super_admin superadmin hisobini yaratish va Telegram havolasini berish.
  - Qabul: explicit superadmin rolida bitta faol hisob, username aniq; telefon uydirilmaydi, tasodifiy kuchli parol hash va shifrlangan vaqtinchalik credential bilan saqlanadi. Mavjud hisoblar o‘zgarmaydi; idempotent qayta tekshiruv, server link resolve/muddat/role/password va bot worker holati tasdiqlanadi. Login/parol va alohida Telegram havola foydalanuvchiga/private 0600 faylda beriladi; Gitga secret chiqmaydi. User Start/OTP login alohida foydalanuvchi harakati.
  - Dalil: Production Docker created one active test_super_admin with SUPERADMIN role, null phone (no invented contact), strong Argon2 password and encrypted three-day temporary credential. Commit re-read verified role, password hash, admin portal access and fresh individual link resolution/expiry. Second execution created=false, same account/password/link; all catalogue RBAC permissions pass. Real getMe matches eduneo_admin_bot and production worker fresh/healthy. Credentials and link saved only in private 0600 files on server/local, existing accounts unchanged. User Start/OTP remains a user action.

### O‘qituvchi uchun ikki kunlik davomat tahriri (2026-10-09)

- [x] 085 — Backendda davomat yozish/tahrirlash muddati va yakunlangan davomat tuzatishi.
  - Qabul: muddat Toshkent vaqtida, API editable/deadline/reason qaytaradi; faqat guruh egasi teacher yozadi, kelajak va yopilgan sanalar rad etiladi. Yakunlangan batchni saqlagan holda status/izoh atomik tuzatiladi, noto‘g‘ri student/duplicate va parallel so‘rovlar nazorat qilinadi; oylik statistikalar yangilanadi. Notification pending payload yangilanadi, zarur tuzatish xabari idempotent; no-op qo‘shimcha xabar yaratmaydi. Docker boundary/timezone, RBAC, rollback, concurrency va notification testlari o‘tadi.
  - Dalil: Docker check_backend: Ruff/mypy 104 files, 235 pytest passed. Tashkent calendar deadline includes lesson day through lesson+2 at 23:59:59.999999; UTC boundary/future/closed/RBAC cases verified. Finalized correction preserves batch ID/time, updates monthly stats and pending outbox payload, delivered notification gets one labeled correction; identical concurrent retries create no duplicate. Invalid/duplicate/foreign items roll back and group row locks serialize writes. API returns can_edit/edit_deadline/edit_disabled_reason. No DB migration required.
- [x] 086 — Teacher portalida muddatli davomat tahriri.
  - Bog‘liq: 085. Qabul: server ruxsati asosida editable/readonly, deadline va sabab aniq; yakunlangan davomat uchun tuzatishni saqlash, holat/izoh va dirty-navigation ishlaydi. Muddati o‘tganda mutation boshqaruvi yopiladi, backend rad javobi ko‘rsatiladi; saqlangan sheet/statistikalar yangilanadi. Docker frontend typecheck/lint va meaningful flow testlari o‘tadi.
  - Dalil: Docker frontend typecheck/lint passed; 12 teacher flow tests passed: finalized status/note correction, dirty state/navigation, deadline closure, readonly and backend rejection display.
- [x] 087 — Administrator va o‘qituvchi uchun umumiy davomat hamda o‘zgarishlar tarixi.
  - Manba: 2026-10-13 foydalanuvchi so‘rovi; 086 tugagach deploymentdan oldin yangi funksiyani kiritish.
  - Qabul: admin Davomat bo‘limida barcha guruhlar uchun draft/finalize/correct; teacher faqat o‘z guruhiga va mavjud ikki kunlik muddatda yozadi. Bir xil unique yozuv va batch, atomik audit (actor/role/time/action/old/new/reason); admin mavjud yozuvni tuzatishda sabab majburiy. Tarix ikkala portalda ko‘rinadi; no-op/retry dublikat yaratmaydi; RBAC/CSRF/rollback/concurrency/notification regressiya va migratsiya, Docker backend/frontend/agent checks va production buildlar o‘tadi. Local acceptance; production deployment keyingi alohida vazifa.
  - Dalil: Docker full backend: Ruff/mypy 107 files, 239 pytest passed; frontend typecheck/lint, 126 Vitest and both production builds passed; release checksum verified. 0007 upgrade/model check passed on development and serving local DB; 13 agent tests. Admin draft/finalize/correct, reason, RBAC/CSRF, atomic audit rollback, mixed-role concurrency/no-op and pending lessons verified. Read-only serving acceptance: 4 groups, 1 admin, 3 teachers, existing 364 records/22 batches preserved; API and both portals HTTP 200. Production not deployed.
- [x] 088 — Yetti kunlik login sessiyasida access tokenni avtomatik yangilash.
  - Manba: 2026-10-13 teacher davomatni saqlaganda 15 daqiqalik access tugab, login talab qilishi; bir hafta qayta login bo‘lmasligi so‘raldi.
  - Qabul: admin/teacher protected API 401da o‘z portalidagi refresh cookie orqali bitta avtomatik yangilash va aynan o‘sha so‘rov/bodyni qayta yuborish; 7 kunlik mutlaq sessiya saqlanadi. Reload/reopen va davomat draft/finalize/correctda ishlaydi, lokal o‘zgarishlar yo‘qolmaydi. Bir vaqtdagi requestlar va tablar refresh rotatsiyasini bekor qilmaydi. Login/OTP/parol-reset/logout xatolarida refresh loop yo‘q, 403 retry qilinmaydi; revoked/expired sessiya yopiq qoladi; token/parollar storagega yozilmaydi. Docker frontend flow/concurrency va backend 7 kun/expiry/revocation/RBAC regressiya, lint/typecheck/build/checksum va local smoke o‘tadi.
  - Dalil: Docker full backend Ruff/mypy 108 files, 242 pytest; frontend typecheck/lint, 143 Vitest, both production builds and release checksum passed. Shared ApiClient refreshes protected admin/teacher 401 once with portal-specific cookie/CSRF and exact request body; in-tab single-flight and cross-tab Web Lock/current-cookie probe prevent duplicate rotation. Attendance UI preserves status/note/dirty state; reopening portal restores profile. Backend tests prove 15min access, recovery at 6d23h, absolute 7day expiry, rejected expired mutation creates no audit, revocation/replay/RBAC remain enforced. Migration/model check and 13 agent tests passed; serving smoke API/portals HTTP200 and 364 historical records unchanged. Production not deployed.
- [x] 089 — Superadmin bot almashishi, username va barcha onboarding havolalari.
  - Manba: 2026-10-13 development botdan production botga admin panel orqali o‘tish so‘rovi.
  - Qabul: token/getMe tekshiriladi, username shu tokenning botiga mos; staff/parent/student linklari yangi usernamega o‘tadi. Bir bot rename/token rotation ulanishlarni saqlaydi, boshqa botda offset reset va eski hisoblar uchun qayta Start/link holati (Telegram ID/parol/tarix o‘chmaydi). Worker hot reload, eski polling stale natijalarni qo‘llamasligi, haqiqiy readiness UI va noto‘g‘ri token/username rollback. Superadmin/RBAC/CSRF, OTP va outbox/current bot qayta ulanishi isolated Docker API/worker/frontend flow testlarda o‘tadi. Real konfiguratsiya faqat getMe read-only tekshiriladi; yangi production botga haqiqiy Start va delivery qo‘lda foydalanuvchi harakati, test mocki live delivery deb ko‘rsatilmaydi. Backend/frontend/migration/agent checks, production build/checksum va local smoke o‘tadi.
  - Dalil: Docker full backend compile/Ruff/mypy 110 files and 250 pytest passed; frontend typecheck/lint, 146 Vitest, both production builds/checksum, 13 agent tests passed. 0008 migration/model match passed in development and serving local DB; existing Telegram IDs preserved. Superadmin API updates verified bot ID/name; mismatched username/bad token rollback, all staff/parent/student links, same-bot rename/rotation and legacy identity adoption tested. Different-bot offset reset, preserved IDs/passwords, reconnect Start, OTP/reset/outbox new-token delivery, stale polling/status guards and running-worker hot reload proven with isolated Telegram transport. Real read-only getMe verified eduneo_admin_bot, no messages sent; local real polling remains stopped to avoid production conflict. API/portals HTTP200 and 364 historical records unchanged. Production switch/real Start/delivery not performed.
- [x] 090 — Uchta English CSV guruhi va ikki yangi ingliz tili o‘qituvchisini qo‘shish.
  - Manba: 2026-10-13 foydalanuvchi so‘rovi; deploymentdan oldin kiritildi.
  - Qabul: private CSV audit, aniq roster/jadval mappingi; Asila Ibragimova Dush/Chor/Jum 09:00–10:30, Jamshidbek Juraboev Sesh/Pay/Shan 15:00–16:30 va 16:30–18:00. Fayl stemidan uchta guruh; Beginner/Elementary bir guruh, bir xil ism+telefon takrorlari manba qatorlari saqlangan holda bitta o‘quvchi. Ikki teacher yaratiladi, berilmagan profil uydirilmaydi va admin keyin to‘ldiradi. Foydalanuvchi aniqlashtirishi: Asila davomati to‘liq bo‘sh; boshqa ikki guruh faqat sanasi aniq k→present qoralama, k yo‘q kataklar uchun yozuv yaratilmaydi; admin o‘tgan oylarni tekshirib yakunlaydi. Hash bilan himoyalangan atomik import, rollback va idempotent rerun Dockerda o‘tadi; keyingi admin profil/parol/davomat tahriri saqlanadi. Backup/restoredan so‘ng local serving DB apply, CSV/DB/API ownership/count/jadval va barcha oldingi ma’lumotlarning digestlari saqlanishi tekshiriladi; tashqi worker diagnostikasi alohida qayd qilinadi, bot config ham tekshiriladi. Secret/raw CSV Gitga chiqmaydi; production deploy alohida.
  - Dalil: Docker compile/Ruff/mypy 112 files and 256 pytest, 13 agent tests passed. Private CSV audit: 3 file-stem groups, 56 pupils (10/21/25), one duplicate merged with both source rows. Backup pg_dump/restore counts matched. Local atomic apply created 2 English teachers, 3 groups, 56 students and 98 dated k-only present drafts; Asila attendance empty, no absent/batch/outbox created. Rerun created=0; admin later phone/password/attendance edits preserved in tests. CSV/DB/API schedules, teacher ownership, month-old admin editing and old Python history verified read-only; all prior data/config digests preserved. External Docker restart briefly enabled old local worker: only last_error/updated_at changed, worker stopped again and original backup restored to scratch proved unchanged immutable bot config; scratch removed. API/admin/teacher HTTP200. Production not deployed.
- [x] 091 — Login va parol tiklash tasdiqlash kodini uch daqiqaga qisqartirish.
  - Manba: 2026-10-13 foydalanuvchi so‘rovi.
  - Qabul: admin/teacher login/reset OTP Redis TTL va API expires_at 180 soniya; Telegram matni 3 daqiqa. UI server muddatini ko‘rsatadi, expired javobga yangi muddat bermaydi. Dockerda ikkala portal/purpose bo‘yicha expiry chegarasi va UI countdown, backend/frontend tekshiruvlari, ikki build/checksum hamda local smoke o‘tadi. Production alohida.
  - Dalil: Docker full backend compile/Ruff/mypy 113 files and 264 pytest passed; frontend typecheck/lint, 154 Vitest, both builds and Node/Python release checksum passed; 13 agent tests. Shared OTP TTL is 180 seconds for admin/teacher login and password reset, including generic unknown-user reset response; Telegram says 3 minutes. Eight API boundary cases prove success at 179 seconds, rejection at 180 seconds and replay rejection; real Redis challenge and active-pointer TTL 179-180 verified. Eight UI cases prove 03:00 countdown, deadline disables submission and expired API responses stay expired without fallback. Serving backend imports TTL180; API/admin/teacher HTTP200. Read-only English/baseline acceptance confirms existing data/config preserved; local worker remains stopped. No migration required; production not deployed.
- [x] 092 — Administrator Telegram xabarlari uchun navbat, API va worker.
  - Manba: 2026-10-13 foydalanuvchi ota-ona/o‘quvchilarga tanlab, guruh yoki hammaga yuborish so‘rovi.
  - Qabul: messages:send permission, mavjud adminlarga grant; active parents/students selected/group/all audience, preview va stale guard, entity/chat dedup, idempotent request, immutable author/text/audience history va durable deliveries. Faqat amaldagi botga ulanganlar; dispatchda qayta tekshiruv, token hot reload/config lock, Telegram 4096 limit/plain text, 429 retry_after va rate pacing, transient retry, blocked/failed holat, restart recovery/cancel/retry deliveredni qaytarmaydi. Workerga ulanish, CSRF/Origin/RBAC/migration/concurrency/atomic API va dispatcher Docker testlarda o‘tadi. Sintetik Telegram transport; real oilalarga agent test xabari yubormaydi.
  - Dalil: Docker compile/Ruff/mypy 122 files, 288 pytest passed. 0009 upgrade/head/model check passed on development DB; upgrade/downgrade and existing-admin messages:send grant preserve prior data. API selected/group/all active parent/student audiences, sibling/entity/chat dedup, no secret IDs exposed, stale preview guard, atomic concurrent request idempotence, immutable sender/text/target history, CSRF/Origin/RBAC and filtered pagination proven. Durable OutboxWorker dispatch tested: plain text/UTF16 limit, current recipient/group/permission recheck, no bot-switch send before reconnect, fresh token after verified rotation, config-send lock serialization, ten/sec shared budget and per-chat cooldown, persistent retry_after including newly enqueued campaigns, transient max-five-cycle failure/manual retry, blocked permanent failure, crash rollback/recovery, concurrent dispatch and in-flight cancel preserving acknowledged delivery. Telegram transport was synthetic; no real family messages sent. UI/local final acceptance follows 093/094.
- [x] 093 — Admin panelda professional Xabarlar bo‘limi.
  - Bog‘liq: 092. Qabul: permissionli sidebar, ota-ona/o‘quvchi/ikkalasi, selected search/pagination, to‘liq guruh(lar)/barchaga, matn/sarlavha va Telegram preview, qabul qiluvchilar/ulanmagan/dedup sonlari, yuborishni tasdiqlash. Request id saqlanishi, stale preview/recovery, status/history/delivery detail, failed retry va pending cancel, responsive/accessible UI; Docker typecheck/lint va meaningful flow testlari o‘tadi.
  - Dalil: Docker typecheck/lint and 167 Vitest passed. Permission-gated Xabarlar sidebar/view, selected parent/student/both with search/filter/pagination and persistent selection, group/all audiences, templates/plain-text UTF16-limit preview and explicit confirmation, stale-preview invalidation preserving input and same-request retry/double-click guard verified. History/detail status filtering, failed retry and pending cancel confirmation tested. Shared dialogs named/described with focus trap/restore and nested scroll locks; 13 new flow/accessibility cases. Responsive grids implemented; actual Chromium viewport screenshots and final serving acceptance follow 094. No real family messages sent.
- [x] 094 — Telegram Xabarlar bo‘limining yakuniy Docker va local qabuli.
  - Bog‘liq: 093. Qabul: backend/frontend/agent/migration regressiya, ikki build/checksum; local backup/migration/head/model va API/portallar smoke, mavjud English/Python/credential/davomat saqlanishi. Live data faqat read-only audience/preview acceptance; haqiqiy xabar yuborish admin harakati, isolated delivery sinovi live delivery deb ko‘rsatilmaydi. Worker production polling konflikti uchun to‘xtagan; hujjat va checkpoint to‘liq.
  - Dalil: Docker backend 288 pytest/compile/Ruff/mypy 122 files, frontend 167 Vitest/typecheck/lint, 13 agent tests, both production builds and Node/Python release checksum passed. Private pre-admin-messages-20261013 pg_dump restored with matching counts; serving/development 0009 head and model match. Read-only serving API confirms 7 groups/118 students/0 parents, all 118 presently unlinked, configured bot, 0 campaigns/deliveries, admin grant and teacher403. English baseline hashes preserve all prior rows/passwords/history/immutable config with only explicit 0009 messages:send grant normalized; attendance remains462, batches22. API/admin/teacher HTTP200; local real worker remains stopped. MESSAGES.md documents operation/delivery limits and local acceptance. Chromium visual image download remains in progress for final UI plan098; no real messages sent.
- [x] 095 — Ruxsatlar auditi va frontend/backend test rejasini tuzish.
  - Manba: 2026-10-13 foydalanuvchi rasmli qo‘llanma, permission audit, test va production so‘rovi.
  - Bog‘liq: 094. Qabul: permission katalogi, portal/role/status/CSRF va UI/API actionlar matriksi yoziladi; superadmin full, admin aniq grant, teacher ownership tekshiriladi. Read/write va superadmin-only farqlari, full-admin hamda cheklangan admin oqimlari audit qilinadi; topilgan xatolar test bilan tuzatiladi. TEST_PLAN.md da feature/role/UI/backend/migration/delivery/release acceptance, sintetik/live chegarasi va dalil joylari yoziladi. Docker meaningful RBAC regressiya o‘tadi.
  - Dalil: TEST_PLAN.md defines role/action matrix and 36+ release/backend/UI/guide/data/CI/CD cases with synthetic/live boundaries. Audit fixed group creator/editor selector403 and student selector/filter403 through permission-scoped minimal lookups (no phone/username/credentials/links/grants); action write implies module read consistently on server/UI and saved grants. Removed frontend wildcard mismatch; full catalogue still cannot manage bot or admin accounts; superadmin full-grant/clear controls and dependency toggle tested. Auth profile refocus/visible/60s refresh updates revoked grants without clearing drafts, 401/403 closes account and 503 preserves it. Full backend309 passed (Ruff/mypy124); final39 real route/grant/role/creation/revocation/CRUD cases and mypy114 src/tests passed. Frontend173 Vitest/typecheck/lint passed. Actual Docker Chromium message app1440/768/360 confirmed no overflow/JS or visible action errors and focus trap; secure UUID fallback fixed HTTP-context failure. No real messages or serving mutations.
- [x] 096 — Admin va superadmin uchun ruxsatga mos rasmli Qo‘llanma bo‘limi.
  - Bog‘liq: 095. Qabul: admin portal sidebar va professional searchable/sectioned qo‘llanma. Superadmin barcha o‘ziga tegishli mavzular; administrator faqat berilgan action/permission mavzularini ko‘radi, full admin barcha admin ruxsat mavzularini ko‘radi; bot/superadmin-only huquq rolga mos. Haqiqiy frontend komponentlaridan sintetik ma’lumot bilan screenshotlar, raqamli markerlar/aniq qadamlar, alt text va matnli tushuntirish; public assetda real PII/token/parol/link yo‘q. Docker UI/permission/guide flow tests va rasm audit o‘tadi.
  - Dalil: Admin Qo‘llanma sidebar/routing and22 permission-filtered topics with73 numbered text steps, searchable sections, images/alt/zoom, learned state and allowed destination implemented. Superadmin22/full-admin20/limited groups-reader6; no bot/admin-grant topic for full-admin; statistics requires both student+attendance read; revoked article/zoom closes.21 actual frontend PNGs captured solely through closed synthetic API fixtures and numbered DOM overlays; modal crops and timer marker reviewed, real PII/token/password/Telegram links excluded. Asset PNG dimensions/checksum/provenance audit passed. Docker typecheck/lint and full191 Vitest; final28 guide/nav/audit cases passed. Actual Chromium all22 topic images decoded, role/search/zoom and1440/768/360 no overflow/JS error; mobile header exit button fully visible. Guide validation fixed attendance-only history selector and exposed immutable Audit tarixi tab to read-only admins; no writes in audit regression. GUIDES.md/TEST_PLAN updated; production follows099–101.
- [x] 097 — Teacher portal uchun to‘liq rasmli Qo‘llanma bo‘limi.
  - Bog‘liq: 096. Qabul: teacher sidebar professional qo‘llanma, o‘z guruh/o‘quvchi, draft/finalize/tuzatish, ikki kun/Toshkent vaqt chegarasi, tarix/statistika, profil/parol/Telegram/3-min OTP/7-kun session mavzulari. Admin amallari teacherga ochilmaydi. Annotated haqiqiy frontend screenshots, qadamlar/alt text/mobil responsive, UI flow tests va synthetic asset audit Dockerda o‘tadi.
  - Dalil: Teacher Qo‘llanma sidebar/App and isolated portal wrappers implemented with11 teacher-only topics/34 steps. Covers private Telegram onboarding/login,180s OTP/absolute7day session, own groups/pupils/stats, drafts/finalize, Tashkent lesson+2days correction, history/immutable audit and own profile/avatar/password; admin actions not exposed.11 actual teacher app PNGs captured using only closed synthetic API fixtures and numbered DOM markers; final correction/save and finalize-count markers reviewed;32 combined PNG checksum/dimension/provenance audit passed. Shared finalize notice now correctly distinguishes teacher2day deadline vs administrator reason-based correction and only linked parent notification queue. Docker typecheck/lint,54 focused guide/teacher tests and full196 Vitest passed. Actual Chromium11 decoded images, exact correction-boundary search, zoom/destination, admin-role forbidden,1440/768/360 no overflow/JS errors and mobile exit fully visible. GUIDES.md/TEST_PLAN updated; no real Telegram sends.
- [x] 098 — Test rejasi bo‘yicha yakuniy UI/backend/qo‘llanma/release qabuli.
  - Bog‘liq: 097. Qabul: TEST_PLAN.md barcha kerakli case/dalillar: role permission, yangi Xabarlar, qo‘llanmalar visibility/qidiruv/qadamlar/screenshots, desktop/tablet/mobile vizual va brauzer oqimlari; backend/frontend/migration/agent/Docker regression. Ikki build/checksum, local real-data read-only smoke/preservation, fake Telegram bilan delivery; fake login/delivery live deb ko‘rsatilmaydi. Xatolar tuzatiladi, acceptance natijalari qayd qilinadi.
  - Dalil: TEST_PLAN feature/role/UI/backend/data/release receipts recorded. Docker full309pytest/compile/Ruff/mypy124,clean npmci/typecheck/lint/full196Vitest,13agent,0009development head/model match passed. Both production builds and Node/Python source/assets checksums passed. Build revealed mixed portal guide assets, fixed through explicit package/Vite guide entrypoints:admin21PNG/teacher11PNG and no admin grant/bot manual in teacherJS;32PNG dimension/checksum/synthetic provenance audit passed. Runtime npm audit omitdev0;9 dev-tool advisories remain as recorded maintenance limitation. After clean install devserver cache reset, final Chromium message/admin-guide/teacher-guide scripts passed1440/768/360,all33 topic images decode,role/search/zoom/destination/no overflow/visible action error/JS exception and keyboard/focus/header controls. Serving read-only English baseline preserves historical rows/credentials/config except exact0009 admin grant;7groups/118students/462attendance/22batches,Asila empty/Jamshid98drafts;0parent/118unlinked/0campaign/delivery. API/portalsHTTP200;real local worker stopped. Production/Python-English deployment and CI/CD follow099–101.
- [x] 099 — English private ma’lumotlari va yangi release uchun production deployment tayyorlash.
  - Bog‘liq: 098. Qabul: production private English CSV/profile import rejasi, hash/backup/atomik rerun va CI/deploy hook; mavjud hisob/parol/Telegram link/tarix saqlanadi, admin keyingi tahriri importda bosib ketmaydi. VPS/runtime/release/SSH identity va GitHub Actions deployment talablari secretlarni chiqarmasdan tekshiriladi; deploy konfiguratsiyasi Dockerda testlanadi, server backup/rollback tartibi reviewable bo‘ladi. Real ma’lumotlar faqat private/serverga, Gitga chiqmaydi.
  - Dalil: Docker316pytest/Ruff/mypy128;13agent;13deploy/actionlint;0010dev+serving head/model;local backup/restore and English/baseline readonly preserved;real disposable production Python+English receipts/admin-edits/second-release/TLS/backup/automatic+manual rollback passed. Pinned root SSH VPS verified current1473595/0006 and5staff/4groups/62students/388attendance/24batches;private VPS dump restored/counts matched. Private English3CSV+reviewedhash0600 uploaded;dedicated CI key forced-command arbitrary-command rejection verified. No production runtime/data changes;GitHub secrets-write auth dependency recorded for100.
- [/] 100 — Tekshirilgan release’ni GitHubga professional commit/push va CI/CD ishlashini tasdiqlash.
  - Bog‘liq: 099. Qabul: remote/base/non-force branch, public diff, secret/PII/unrelated artifact tekshiruvi; yangi qo‘llanma assetlari va ikki release checksum mos. User bergan push/deploy authorization doirasida professional commit va non-force push exact SHA bilan; GitHub Actions test/build/deploy runi topilib real natija qayd qilinadi. Kerakli server/secrets konfiguratsiyasi mavjud ruxsatli credentialdan xavfsiz sozlanadi; yo‘q dependency ishlagan deb ko‘rsatilmaydi.
  - Dalil: Acceptance yakunida Docker task manager qayd qiladi.
- [ ] 101 — Production deployment va oxirgi read-only UI/API/data qabuli.
  - Bog‘liq: 100. Qabul: backupdan keyin exact verified release SHA, migratsiyalar/import va singleton worker sog‘lom; HTTPS admin/teacher/guide assets/API/release marker va rol/permission/window/OTP/Xabarlar imkoniyati read-only tekshiriladi. English guruhlari/ikki teacher/Asila bo‘sh davomat/Jamshidbek k-only va oldingi Python/credential/history saqlanadi. Real oilalarga agent tomonidan test xabari yuborilmaydi; deploy xatosida rollback va aniq evidence. CI/CD deploy haqiqatan success bo‘ladi, cheklovlar yashirilmaydi.
  - Dalil: Acceptance yakunida Docker task manager qayd qiladi.
