# NeoAvlod LMS release test rejasi

Manba: 2026-10-13 rasmli qo‘llanmalar, permission audit, UI/backend sinovi va
GitHub CI/CD orqali production talabi. Tartib TASKS.md 095–101; release natijalari
shu faylning qabul jadvaliga yoziladi. Bajarilmagan sinov “o‘tdi” deb belgilanmaydi.

## Ruxsat va rol matriksi

2026-10-14 kengaytma: AUDIT_PLAN.md va TASKS103–114 bo‘yicha quyidagi case
matriks qo‘shildi.103–111 dalillari quyida qayd qilinadi;112–114 hali yakunlanmagan.
Davomat o‘zgarish auditi yangi talab bo‘yicha faqat superadmin,
oddiy davomat tarixi/statistikasi esa mavjud biznes huquqlarida qoladi.

| ID | Audit/DOM qo‘llanma sinovi | Qabul |
| --- | --- | --- |
| L01 | Subject/group/student/staff/assignment/profile/bot/campaign mutations | Verified actor snapshot, entity/action/old-new/sabab, UTC precision va Tashkent kun; atomik yozuv |
| L02 | Audit capture failure/no-op/parallel transaction | Business rollback; no-op mutation yo‘q, retry/concurrent commit event yo‘qotmaydi |
| L03 | Login/OTP/reset/logout/refresh/Telegram/worker | Haqiqiy provenance va outcome; OTP/token/parol/hash/cookie/link logda yo‘q |
| L04 | Read/403/422/5xx, caller spoof | Server identity/correlation; raw body/query/IP proxy spoof yoki actor inputga ishonch yo‘q |
| L05 | Har rol uchun attendance correction reason | Existing status/note o‘zgarsa sabab, first-entry/no-op/finalize farqi, old-new actor/time |
| L06 | Super/full-admin/teacher/anon/inactive/expired | Faqat faol superadmin logs va eski attendance auditga200; qolganlar403/401 |
| L07 | API/DB/folder immutability | Delete/edit endpoint yo‘q; runtime SQL UPDATE/DELETE/TRUNCATE rad; API FS read-only |
| L08 | Archive crash/disk full/retry/orphan/two workers | Fsync/read-back/metadata oldin prune yo‘q; yo‘qotish/dublikat va watermark skip yo‘q |
| L09 | Encryption/key/payload/path/symlink/corruption | Authenticated decrypt/checksum/count/IDs; safe regular private file; tamper fail-closed |
| L10 | Kunlik filters/cursor/download/snapshot | Toshkent boundary, seconds, persisted+pending dedup, safe attachment/no-store; download ham audit |
| L11 | Bounded memory/compression | Synthetic large day streaming, max batch/payload, measured compression; doimiy DB payload arxivga o‘tadi |
| L12 | Upgrade/redeploy/business rollback | Audit schema/folder/key/dalil saqlanadi; old credentials/history/import receipts o‘zgarmaydi |
| H01 | Dashboard welcome yo‘q | Faqat asosiy ko‘rsatkichlar; profil/sidebar/navigation ishlaydi |
| H02 | Tailwind latest stable/lock/build | Rasmiy upgrade/compatibility, Docker registry, ikki portal va shared source classes |
| H03 | Barcha React scene/marker/qadamlar | Shared React UI/SVG tiniq zoom, read-only/inert synthetic previews, raster dependency yo‘q |
| H04 | Demo network va privilege isolation | Preview API/mutation/secret yo‘q; teacher bundle log/bot/grant materialini olmaydi |
| H05 | Guide role/search/zoom/revocation/mobile | Superadmin logs topic, admin/teacher audit topic yo‘q;1440/768/360 klaviatura/overflow/JS checks |

105 qabul dalili: Docker registry Tailwind4.3.3/@tailwindcss-vite4.3.3 va
Vite8.3.4/Reactplugin6.1.2, Node22.23.3; root/workspace deps deduped, npm audit
0 advisories. Shared CSSfirst/source/theme; utility compatibility va teacher
mobile header min-width/shrink tuzatildi.196 full Vitest, typecheck/lint, ikkala
build; yakuniy teacher9 flow va actual guide1440/768/360 qayta passed.32 actual
synthetic app ekranlari private tailwind-105da; message/admin guide/dashboard
brauzer oqimlari passed. Yangi React qo‘llanma111da shu sinovlarni almashtiradi.

Barcha endpointlar faol xodim va tirik sessionni tekshiradi. Admin endpointlari
admin portal sessiyasini, teacher endpointlari teacher rolini talab qiladi.
Yozish so‘rovlari Origin va sessionga bog‘liq double-submit CSRFni tekshiradi.
O‘chirilgan/revoked/expired hisob 401; tirik hisobda ruxsat yo‘q bo‘lsa 403.
Teacher begona guruh/o‘quvchisiga mavjudligini oshkor qilmaydigan 404 oladi.

| Bo‘lim/amal | Superadmin | Administrator | Teacher |
| --- | --- | --- | --- |
| Dashboard | Hammasi | Faqat tegishli grantga mos hisoblar | O‘z guruhlari |
| Xodimlar | staff:manage, admin/teacher va admin grantlari | staff:manage, faqat teacher boshqarish | Yopiq |
| Fanlar | Barcha amallar | subjects:manage | Yopiq |
| Guruhlar | Barcha amallar | groups:read/create/edit alohida | Faqat o‘z guruhini ko‘rish |
| O‘quvchilar | Barcha amallar | students:read/create/edit alohida; edit ko‘chirish/status/link amallarini ham beradi | Faqat o‘z guruhidagi profil/statistika |
| Davomat tarixi | Barcha guruhlar | attendance:read | O‘z guruhlari |
| Davomat yozish/tuzatish | Barcha guruhlar, eski sana sabab bilan | attendance:write, eski sana sabab bilan | O‘z guruhi; dars sanasidan keyingi 2-kun oxirigacha, Toshkent vaqti |
| Telegram xabarlar | Barcha faol auditoriya | messages:send | Yopiq |
| Bot sozlamalari | Faqat shu rol | Hatto full grant bilan yopiq | Yopiq |
| Shaxsiy profil/parol | O‘z hisobi | O‘z hisobi | O‘z hisobi |
| Qo‘llanma | Barcha superadmin mavzulari | Faqat berilgan amallarga mos mavzular | Teacher mavzulari |

Write/create/edit grant o‘z modulining read grantini ham beradi. Yangi admin
grantlari saqlanganda normalizatsiya qilinadi; eski hisoblar uchun server va UI
shu bog‘liqlikni bir xil hisoblaydi. Read olib tashlansa staff UI unga bog‘liq
yozish grantlarini ham olib tashlaydi. Full admin — katalogdagi barcha 11 kalit;
`*`, noma’lum yoki boshqa registrdagi kalitlar to‘liq ruxsat bermaydi.

`/admin/lookups/group-options` groups read/create/edit uchun faqat fan
id/nom/faollik va teacher id/ism/faollikni qaytaradi. Staff username, telefon,
permission yoki bot havolasi berilmaydi; boshqa modullarni boshqarish ochilmaydi.
`/admin/lookups/student-groups` student read/create/edit uchun faqat faol guruh
id/nom/sig‘im/band sonini qaytaradi. Tanlovlar 100 ta bilan jimgina kesilmaydi.

## Izolyatsiya va sinov ma’lumotlari

- Barcha runtime/test/migration/build Dockerda. Backend test DB — alohida
  `neoavlod_test`; har bir model fixture tozalanadi. Testlar serving DBni yozmaydi.
- Brauzer actual admin/teacher appni ochadi, barcha `/api/**` so‘rovlarini
  sintetik fixture bilan intercept qiladi. Bekor qilingan noma’lum endpointlar
  real backendga uzatilmaydi. Ismlar “Namuna”, telefonlar namuna yoki bo‘sh.
- Telegram HTTP transporti sintetik; bu real /start, OTP yoki yetkazish dalili
  sifatida talqin qilinmaydi. Agent oilalarga test broadcast yubormaydi.
- Serving acceptance SQL tranzaksiyasi `READ ONLY`; POST faqat preview, navbatga
  qo‘shish yo‘q. PII, parol, token, raw CSV, Telegram ID, capability linklar
  private dalillarda; public screenshotlarga yoki Gitga chiqmaydi.

## Bajariladigan case va dalillar

| ID | Sinov | Kutilgan natija / avtomatlashtirilgan dalil |
| --- | --- | --- |
| P01 | Har bir grant, grantsiz, full, wildcard, noma’lum | Haqiqiy 8 API route matriksi; test_permission_audit.py |
| P02 | Superadmin/teacher/inactive/revoked/demoted | 200/403/401 va ownership404; test_rbac.py, test_sessions.py |
| P03 | Cheklangan guruh creator/editor | Selector ishlaydi, unrelated staff/fan boshqaruvi403; test_permission_audit.py |
| P04 | Student creator/editor | Sig‘im selector, group management403, grant bekor qilinsa darhol403 |
| P05 | Staff boshqarishda rol ko‘tarish | Admin faqat teacher; superadmin admin grantini o‘zgartiradi; oxirgi superadmin saqlanadi |
| P06 | Read/write va full admin UI | Sidebar/tugma/mavzu bir xil dependency; bot faqat superadmin; admin-shell/staff/academic/student testlar |
| P08 | Ochiq panelda grant yangilanishi | Refocus/visible/60soniya profile refresh; qoralama/spinner reset yo‘q;401/403 hisob yopiladi,503da form saqlanadi |
| P07 | CSRF/Origin/portal | GET ruxsati mutationga yetmaydi; noto‘g‘ri header/cookie/origin403; backend regressiya |
| A01 | Admin/teacher bir xil davomat | Draft/finalize/correct atomik, teacher ownership va 2 kun; test_admin_attendance/edit_window |
| A02 | Eski sana va audit | Admin sabab majburiy; old/new/actor/time/action; no-op/retry dublikat yo‘q |
| A03 | Sessiya 15min/7kun va ko‘p tab | Automatic refresh ayni payload bilan; form saqlanadi; 7kun mutlaq; backend+client-refresh/attendance-session |
| A04 | OTP login/reset, ikki portal | 179soniya qabul,180rad, replayrad; UI03:00→00:00; test_otp_expiry/otp-expiry |
| B01 | Bot rename/token/boshqa bot | getMe identity, yangi link, samebot ulanish saqlanishi, newbot Start, stale ack himoyasi |
| M01 | Parent/student/both; selected/groups/all | Active roster, siblings/entity/chat dedup, orphan/inactive chiqariladi; test_messages.py |
| M02 | Preview/stale/request retry | Matn/ro‘yxat o‘zgarsa fresh preview; requestid retry saqlanadi; atomic concurrent enqueue |
| M03 | Qidiruv/pagination/limit | Tanlov saqlanadi; full formatted UTF16≤4096; kerak bo‘lmasa yuborish disabled |
| M04 | Tasdiqlash/tarix/detail | Explicit confirmdan oldin send yo‘q; actor/text/audience immutable; status/attempt/vaqt |
| M05 | Failed retry/pending cancel | Delivered qayta yuborilmaydi; faqat xatoli yoki navbatdagi; in-flight cancel serialization |
| M06 | Worker/restart/bot/rate/error | 10/sec,1/chat/sec,429 persisted pause,5 transient retry; fresh token, reconnect/permissions recheck |
| G01 | Admin rol va grant mavzulari | Grantsiz umumiy mavzular; har bir grant uchun action mavzusi; fulladmin bot mavzusi yo‘q |
| G02 | Teacher to‘liq mavzulari | Guruh/profil/statistika/davomat/tarix/session/OTP, admin boshqaruvi yo‘q |
| G03 | Qo‘llanma qidiruv va bo‘lim tanlash | Ism/keyword/step bo‘yicha; unauthorized mavzu searchda ham chiqmaydi; empty state va reset |
| G04 | React namuna va raqamli qadam mosligi | Shared UI atomlari, inert namuna; marker1..N qadamga mos; accessible description, matnli qadam, raster asset yo‘q |
| G05 | Ruxsat o‘zgarsa ochiq qo‘llanma | Oldingi mavzu yopiladi, yangi topics qayta hisoblanadi; stale selection ochilmaydi |
| U01 | 1440/768/360px | Sidebar/mobile menu, guide/topic/card/grid/dialog; horizontal overflow yo‘q; private screenshot review |
| U02 | Klaviatura va matn | Nomlangan dialog, focus trap/restore, Tab/Escape, form labels, alt; shared modal tests+browser |
| U03 | Console/network | JS exception yo‘q; native React previews APIga tegmaydi; sintetik script orqali to‘liq UI oqim; API spy unknownblocked |
| D01 | Migratsiya | Upgrade/downgrade/head/model match, eski FK/credential/history saqlanadi; test_migrations.py |
| D02 | Haqiqiy private import | Hash/backup restore, rerun0, Asila bo‘sh, Jamshid k-only98; admin keyingi tahriri saqlanadi |
| R01 | Full Docker gate | check_backend/frontend/agent, pytest/Vitest, release build/checksum; TASKS evidence |
| R02 | Public diff | Secret/PII scan, unrelated output excluded, no force push, exactSHA remote mos |
| R03 | CI/CD | Actions test/build/deploy haqiqatan success; pinnedSSH; private source faqat serverda; runURL+SHA |
| R04 | Production | Backup→exactSHA→migrate/import→healthy singletonworker; HTTPS/API/guideassets/release marker; read-only data reconcile |
| R05 | Rollback | Mavjud deploy sinovi rollback; xato bo‘lsa old verified release; schema/data mosligi, secretlar saqlanishi |

## Buyruqlar

`scripts/agent_skills/check_backend.sh`, `check_frontend.sh`,
`check_agent_skills.sh`, `run_migrations.sh`; `docker_env.sh node npm test`;
`scripts/deploy/build_frontend.sh`, Node `prepare-release.mjs --check` va
Docker Python `scripts/deploy/verify_frontend.py /workspace/frontend`.
Brauzer: `scripts/agent_skills/browser.sh scripts/agent_skills/browser_messages.cjs`;
guide/role browser cases qo‘llanma implementation bilan qo‘shiladi. Private
screenshots `.private/ui-acceptance/`; public guide rasmlari faqat sintetik auditdan
keyin frontend assetsga ko‘chiriladi.

Local DB: `real_data.sh backup <unique-name>` → `real_data.sh migrate` →
read-only `verify_english.py --baseline ... --allow-message-grant` va
`verify_messages.py`. Local bot worker production bilan polling qilmaydi.

## Qabul natijalari

| Bosqich | Holat | Dalil |
| --- | --- | --- |
| 092–094 Xabarlar backend/UI/local | O‘tdi | 288 pytest,167 Vitest,13 agent;0009; ikki build/checksum;118 unlinked,0 sends |
| 095 permission audit | O‘tdi | Full309 backend; final39 API/RBAC/CRUD,173 Vitest/typecheck/lint; minimal lookup/write→read/full-grant/refocus verified; Chromium1440/768/360 Xabarlar,0 visible error/overflow/JS exception |
| 096 admin qo‘llanma | O‘tdi | 22 mavzu/21 numbered real-UI synthetic screenshot; superadmin22/fulladmin20/limited6; grant/search/zoom/revocation16 tests; full191 Vitest/typecheck/lint; Chromium3 viewport/barcha image decode |
| 097 teacher qo‘llanma | O‘tdi | 11 mavzu/11 numbered actual-UI synthetic screenshots; full196 Vitest/typecheck/lint; teacher-only/search2-kun23:59/zoom/destination/11image decode/3viewports;32asset audit |
| 098 full UI/backend/release | O‘tdi | Full309pytest/Ruff/mypy124,clean196Vitest/typecheck/lint,13agent,0009head/model,real-data-preservation/preview read-only;2build/Node+Python checksum/32PNG/portal-scoped assets; final3 browser scripts passed |
| 099 production tayyorlov | O‘tdi | 316backend/Ruff/mypy128;0010head/model;13agent/13deploy/actionlint; real disposable production Python+English receipt/repeat/admin-edits/TLS/rollback; VPS private backup scratch restore5staff/4groups/62students/388attendance/24batches; restricted CI SSH key verified; English private package0600 serverga yuborildi |
| 100 GitHub/CI/CD | O‘tdi | c3f78986b2dc15962ee51c1603525c29c2962cd0 non-force main push; [Actions38503421183](https://github.com/software-engineer006/NeoAvlodLMS/actions/runs/38503421183) test va real deploy SUCCESS.322backend/196frontend, release checksums, role/receipt/regression/TLS;5SSHsecrets configured, pinned restricted CI key |
| 101 production qabul | O‘tdi | Actual pre-release dump scratch restore; original5staff/4groups/62students/388attendance/24batches digests unchanged. Production6staff/7groups/118students/486attendance/24batches, English3groups56pupils98k-onlydrafts/Asilaempty.0010, GETAPIrole/ownership,OTP180/15min+7days,realgetMe+workerready,HTTPS42assets/32PNG checksums,0campaign/delivery/outbox/send. Production bundle isolated browser33topics/3viewports/search/zoom/message-confirm passed |

100 keyingi sozlama: user aynan mavjud CI keyni GitHub repo secretiga saqlashni
aniq buyurdi; saving-existing-credential tasnifi bilan5SSHsecret saqlandi va
metadata tekshirildi. Attempt2 SSH/build/checksum/backup/0006→0010migration va
Python adopted(created0) o‘tdi. Englishda mavjud teacher firstname qo‘shimchasi
strict profile conflict berdi; automatic rollback eski app/web1473595ni tikladi,
English transaction yozilmadi. Read-only metadata orqali sabab topildi; yangi
preserve_given_names fix6case bilan full322backend/Ruff/mypy128 va frontend
checksum/publicscan o‘tdi. Latest fix commit/CI va101production qabul kutilmoqda.

### 101 production dalillari (2026-10-14)

- Actual exact release c3f78986b2dc15962ee51c1603525c29c2962cd0, successful
  GitHub deploy115656963055. Server private pre-release dump scratch restore
  successful; original staff/profile/password/Telegram ID/auth UUID, Python
  roster/source fields, all388old attendance and24batches unchanged by row digest.
- Current6staff/7groups/118students/486attendance/24batches. Existing Asila teacher
  account reused without profile/password changes, new Jamshidbek teacher created;
  source schedules/56pupil fields and98dated present drafts reconcile exactly.
  Asila attendance and new English batches empty;0campaign/delivery/outbox.
- Actual production API code with readonly DB/session and scoped ASGI identity
  overrides checks admin GET200, teacher own1/2groups, admin403/foreign404 and
  anonymous401. This does not claim new real OTP logins for teachers. Bot real
  getMe username verified, immutable token/version/config preserved, singleton
  polling worker heartbeat ready. Legacy bot identity metadata may stay unset
  until the next verified settings update; existing links remain functional.
- Public HTTPS/admin/teacher release markers exact; all26admin+16teacher assets
  match SHA256 including21admin+11teacher guide PNGs. Runtime package source
  confirms15min access, absolute7day refresh family and shared OTP180seconds.
- Production HTTPS frontend bundles tested in separate Docker Chromium with
  closed synthetic API fixtures: admin22/fulladmin20/limited6,teacher11,
  all33topic images decode, search/zoom/destination/admin-denied, message
  preview/confirmation/focus,1440/768/360 no overflow or JS errors. Real production
  API writes and Telegram sends are blocked by the fixture; private screenshots
  in .private/production-ui. Native Chrome existing superadmin session shows
  the new navigation, but native screenshot/interaction race was excluded from
  visual evidence. This browser test does not claim real teacher authentication.
- Actual source receipts invoked in readonly DB transaction, no writable
  credential mount and forbidden provisioning callback: Python and English
  both already_applied/created0. Scratch verification DB removed; local real
  polling remains stopped; private files/source CSVs are excluded from Git.

### 098 final case dalillari (2026-10-13)

- P01–P08: `test_permission_audit.py`21 case va real endpoint matritsi; existing
  RBAC/staff/group/student/session/CSRF regressiyasi full309pytestda o‘tdi.
  UI fullgrant, dependent read, wildcard rejection va refocus/grant revocation
  draft preservation sinovlari full196Vitestda o‘tdi.
- A01–A04/B01/M01–M06: full backend309 va frontend196: audit/concurrency/
  rollback, teacher window, session refresh/absolute7days, real Redis180TTL,
  bot identity/hot reload/reconnect, message durable retry/pacing/cancel/input
  recovery. Telegram transport sintetik; haqiqiy oilaga test yetkazish qilinmadi.
- G01–G05/U01–U03: admin guide22/fulladmin20/limited6; teacher11/admin-denied,
 33 topic image decode (32 unique PNG), search/section/zoom/permission-safe
  destination; 1440/768/360px barcha3 script no overflow/visible action error/
  JS exception. Modal keyboard/focus va header exit fully-visible tekshirildi.
  Rasmlar .private/ui-acceptance dagi viewport dalillari bilan ko‘zdan kechirildi.
- D01–D02:0009 development/serving head/model match; migration upgrade/downgrade
  regressiyasi, private backup restore bir xil count. Read-only English baseline
  rows/credential/history/immutable config preserved; faqat0009ning yangi
  messages:send admin granti normalizatsiya istisnosi. Local 6staff/7groups/
  118students/462attendance/22batches, Asila empty/Jamshid98k-only drafts,
  0parent/118unlinked/0campaign/0delivery. Serving API va ikkala portal HTTP200.
- R01: clean npmci/typecheck/lint/full196Vitest/2build,309backend/13agent,
  Node+Python checksum,32PNG audit. Builddagi aralash portal assets tuzatildi:
  admin21PNG/teacher11PNG; teacher JSda administrator grant/bot manual yo‘q.
  `npm audit --omit=dev` runtime vulnerability0; full installning9 dev advisory
  warningi major toolchain upgrade doirasiga kiradi, runtime/static production
  paketiga tegishli emas. Public diff whitespace check passed.
- R02–R05: user authorized push/deploy, lekin exact commit/Actions/VPS dalillari
  099–101da olinadi. Local real bot worker polling konflikti uchun stopped.

## 2026-10-14 audit va React qo‘llanma dalillari (103–111)

Oldingi 095–102 PNG va rol qabul qaydlari tarixiy release dalilidir. Joriy
qo‘llanma33 React mavzu (admin23/fulladmin19/limited6/teacher10), rastrsiz.
L01–L11: whitelist PostgreSQL capture/seconds/Tashkent/snapshots, business
rollback/noop/concurrency/actor-spoof/auth/CSRF/reason, exclusive superadmin
GET-only API va legacy audit denial, runtime/archiver privileges, immutable
folder/hash/key/fsync/exact-prune faultlar Dockerda tasdiqlandi. Full356backend
va final15API boundary/memory cases,11archive faults, extra21capture/API/
migration tests learner-name snapshotdan keyin o‘tdi.128x30KB archival peak
<40MiB,8192x5KB export <12MiB traced Python RAM; compression fixture<1/8.
Actual Docker readonly audit mount write/unlink/chmodni rad etdi.

H01–H05/G01–G05/U01–U03: latest locked Tailwind4.3.3/Vite8.3.4, dashboard
welcome removed. Logs browser filters/diffs/reason/seconds/CSRF gzip download
and admin/teacher hidden/reason enforcement1440/768/360 passed. Full207UI
followed by54 guide-specific/full240Vitest/typecheck/lint passed. All33 scenes
have exact sequential markers, inert readonly keyboard-free controls, no
network/credentials or PNG. Actual guide browser search/zoom/inert/font16+
role/destination/all topics and1440/768/360 no overflow/JS errors passed;
synthetic captures visually reviewed.32 public PNG removed; GUIDES.md and
source-checksum/provenance audit updated. Clean builds/release checks and
local-data/production rollback verification are finalized in112–114.

2026-10-14 audit final acceptance: full362 PostgreSQL/backend tests,
Ruff/mypy145 files,240 frontend tests including54 guide cases,13 agent cases,
clean builds and Node/Python source+asset checksums passed. Actual closed
synthetic Chromium covers all33 React guide scenes and Logs/attendance reason
flows at1440/768/360. Local pre-audit backup restored to scratch, all public
business/credential hashes matched;0012 upgrade/model match and23 actual-data
read-only ownership/role API checks passed without real login or sends.

Production infrastructure113:15 deployment/rollback unit+actionlint cases,
12 archive fault/security cases and actual disposable TLS production integration
passed. UID1000 API/worker/archiver; restricted LOGIN app role not superuser;
encrypted104-event read-back, API readonly mount/direct DELETE denial,
persistent files/key hashes unchanged after two releases, automatic Nginx-error
rollback and manual rollback, checked pg_dump plus private archive/key backup.
Unsafe pre-audit rollback denied, evidence retained and compatible runtime
restarted. Production VPS previous release/readiness and private backup listing
verified; baseline6staff/7groups/118students/486attendance/24batches/0messages,
private persistent0700folder and stable new secrets ready.213 public staged
paths scanned:98 actual pupil names/credentials/capability links/raw CSV and
unrelated output absent. Real CI/CD and production role/UI acceptance114 next.
