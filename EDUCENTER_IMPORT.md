# Educenter — to‘rtta Python guruhi

Reja: [TASK.md](TASK.md). Dalillar va checkpoint: [TASKS.md](TASKS.md), 076–080.

## Local natija

Fan: **Python dasturlash&vibecoding**. Guruh nomi CSV faylining `.csv`siz nomi.

| Guruh | O‘qituvchi | Kunlar | Vaqt | O‘quvchilar |
|---|---|---|---|---:|
| Python&vibecoding 1-gruh | Jasurbek | Dush, Chor, Juma | 14:30–16:00 | 29 |
| Python&vibecoding 2-gruh | Jasurbek | Dush, Chor, Juma | 16:30–18:00 | 9 |
| Python&vibecoding 3-gruh | Dilmurod | Sesh, Pay, Shanba | 09:30–11:00 | 9 |
| Python&vibecoding 4-gruh | Dilmurod | Sesh, Pay, Shanba | 16:00–18:00 | 15 |

2026 sentabr–oktabr CSV tarixi: 22 dars, 364 aniq davomat yozuvi
(209 keldi, 155 kelmadi). `k`/`K` — keldi, bo‘sh **sana qo‘yilgan dars katagi**
— kelmadi. Sana qo‘yilmagan ustunlar hisobga olinmaydi. Foydalanuvchi ko‘rsatmasi
bilan 3-guruh «23» ustuni tarixdan chiqarilgan, raw manbada saqlanadi.
4 ta boshqa belgi (`p`, `1`, matnli izohlar) aniqlashtirilmagan: neytral katak,
private audit va o‘quvchi profilidagi manba izohida saqlanadi.

Ism to‘liq asl ko‘rinishda saqlanadi, familiya/ota-ona/yosh/narx uydirilmaydi.
5 ta noaniq ko‘p telefonli kontakt raw va profil izohida saqlanadi, asosiy telefon
null. Oddiy telefonlar E.164 ga normallashtiriladi. CSVdagi mygov/maktab holati
LMSdagi faol/nofaol statusga taxminan aylantirilmaydi.

Hisoblar: `ceo_mohira` — superadmin, `teacher_jasurbek` va `teacher_dilmurod`
— teacher. Mavjud hisoblarning paroli, Telegram bog‘lanishi va login oqimi
o‘zgartirilmaydi. Yangi xodimlarni superadmin «Xodimlar» bo‘limidan yaratadi.
Yangi DBda kriptografik parollar yaratiladi va faqat private 0600 faylga yoziladi.
Telegram/OTP login uchun bot konfiguratsiyasi va hisob egasining `/start`i kerak;
bot sozlanmasidan ham data import ishlaydi.

Tekshirilgan local hisoblar va linklar: `.private/python-groups/HISOBLAR.md`
(0600). Jasurbek hali Telegramga ulanmagan bo‘lsa shu fayldagi havolada Startni
bosadi. Mohira va Dilmurodning mavjud Telegram bog‘lanishlari saqlangan.

Local portallar: [Admin](http://localhost:3000),
[Teacher](http://127.0.0.1:3001). Ishga tushirish:

```bash
scripts/agent_skills/local_demo.sh up
scripts/agent_skills/real_data.sh exec python -m neoavlod.educenter_import \
  --source /workspace/educenter_data \
  --credentials /workspace/educenter_data/prepared-accounts.json \
  --report /workspace/.private/python-groups/plan.json
```

Dry-run stdout faqat sonlar va `plan_sha256` chiqaradi. DB o‘zgarmaydi.
Applydan oldin backup (nom har safar yangi bo‘lsin):

```bash
scripts/agent_skills/real_data.sh backup pre-python-groups-20261009
scripts/agent_skills/real_data.sh exec python -m neoavlod.educenter_import \
  --source /workspace/educenter_data \
  --credentials /workspace/educenter_data/prepared-accounts.json \
  --apply --expected-plan REVIEWED_SHA256
scripts/agent_skills/real_data.sh exec python /workspace/scripts/agent_skills/verify_educenter.py
```

`REVIEWED_SHA256` o‘rniga dry-run hashini yozing. Import bir tranzaksiyada;
qayta apply yangi yozuv yaratmaydi, finalized tarix yoki manba/jadval konflikti
bo‘lsa hech narsa yozilmaydi. CSV keyin tahrirlansa explicit reconciliation
kerak; deploy foydalanuvchi kiritgan o‘zgarishlarni jim almashtirmaydi.

## Server va git push orqali CI/CD

Mavjud `.github/workflows/ci-cd.yaml` main branchga pushda Docker testlarni
bajaradi, so‘ng `production` environment orqali aynan tekshirilgan SHAni
deploy qiladi. SSH/known-host/GitHub environment sozlamalari [DEPLOYMENT.md](DEPLOYMENT.md)da.

Serverda bir marta private paketni `/opt/neoavlod/private/educenter_data/`ga
xavfsiz uzating: 4 CSV, `staff-profiles.json` va dry-runda tekshirilgan
`plan.sha256`. CSV/credential/tokenlar Gitda bo‘lmaydi. Custom joy uchun server
deployment muhitida `EDUCENTER_DATA_DIR`ni belgilang. Papka berilib mavjud
bo‘lmasa deploy xato bilan to‘xtaydi; default papka yo‘q bo‘lsa data import
sozlanmagan deb hisoblanadi va odatiy deploy davom etadi.

Tayyor local paket: `.private/python-groups/deploy-package/`.
Undagi `educenter_data/`ni serverdagi `/opt/neoavlod/private/educenter_data/`ga,
`educenter-state/`ni esa `/opt/neoavlod/private/educenter-state/`ga birinchi
importdan oldin xavfsiz ko‘chiring. Directorylar 0700, fayllar 0600. State
paketi localda tekshirilgan parollarni yangi DB uchun saqlaydi. Ishlayotgan
serverning mavjud state faylini bu paket bilan qayta yozmang. Paket Gitga
qo‘shilmagan va hech qayerga yuborilmagan.

Production image bilan dry-run (server Dockerda):

```bash
scripts/deploy/appctl.sh run --rm -T --no-deps \
  -v /opt/neoavlod/private/educenter_data:/import-source:ro \
  migrations python -m neoavlod.educenter_import --source /import-source \
  --credentials /tmp/unused-credentials.json
```

Stdoutdagi tekshirilgan hashni `plan.sha256`ga yozing (faqat 64 hex belgi).
Yangi birinchi server deployda image hali bo‘lmasa release runtime imageini
`compose_release`/Docker orqali build qilib shu dry-runni bajaring.
Local va production rejasi bir xil bo‘lsa local dry-run hashini ishlatish mumkin.

Har deploy tartibi: DB backup → eski API/worker to‘xtashi → migratsiya →
private import → yangi API/worker → health/TLS. Import xatosi yangi releaseni
faollashtirmaydi; eski ilova tiklanadi. Importning o‘zi atomik. Keyingi
health/NGINX xatosida DBdagi muvaffaqiyatli import saqlanadi (kod rollbacki
DB restore qilmaydi); pre-deploy dump tiklash uchun mavjud.

Import holati serverda `/opt/neoavlod/private/educenter-state/`ga yoziladi:
`prepared-accounts.json`, `links.json`, `last-plan.json`. Oldingi hisoblar
bo‘lsa generated paketdagi parol ularning amaldagi paroli hisoblanmaydi;
ularning mavjud paroli saqlanadi. Local hisoblarni bir xil parol bilan
bootstrap qilish kerak bo‘lsa, faqat yangi DBga birinchi importdan **oldin**
mos private credential paketini shu state papkasiga xavfsiz qo‘ying.

CI haqiqiy PIIga bog‘lanmagan: backend sintetik PostgreSQL testlari va real
disposable production deploy ikki marta importni, sonlar o‘zgarmasligini,
import xatosida rollbackni tekshiradi. Haqiqiy VPS va GitHub Actions runi
local tekshiruvdan alohida tasdiqlanadi.
