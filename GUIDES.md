# Rasmli portal qo‘llanmalari

Admin paneldagi Qo‘llanma faqat faol admin/superadmin hisobiga ochiq. Mavzular
`hasPermission` bilan haqiqiy modul/action grantiga mos filtrlanadi. Ko‘rish va
yozish mavzulari alohida; student statistikasi students:read va attendance:read
birga bo‘lganda chiqadi. Full-admin bot sozlamalari yoki admin grantlarini berish
mavzusini ko‘rmaydi — bu ikkalasi superadmin roliga tegishli. Grantsiz admin o‘z
login/profil/session va umumiy panel yo‘riqnomalarini ko‘radi.

Qo‘llanma bo‘lim/qidiruv, mundarija, rasmni kattalashtirish, raqamli matnli
qadamlar, oldingi/keyingi mavzu va ruxsatli bo‘limga o‘tishni qo‘llaydi.
“Tushundim” belgisi shu ochilgan qo‘llanmaning xotirasida turadi; yopib qayta
ochilganda o‘rganilgan soni yangidan boshlanadi. Ruxsat bekor qilinsa ochiq
mavzu/zoom ham filtrdan chiqadi. Panel fokus/visible yoki faol oynada60s profilni
yangilaydi, formani unmount qilmaydi; backend har bir amalda grantni tekshiradi.

Rasmlar haqiqiy frontend komponentlari va app routingidan olingan. Docker
Chromium `/api/**`ni sintetik fixture bilan tutadi; frontenddagi `/src/api/...`
modullari odatdagidek yuklanadi, haqiqiy backend APIga fallback yo‘q. Noma’lum
API so‘rovi403 bilan yopiladi va capture acceptance fail qiladi. “Namuna” hisob,
English A guruhi, nol bilan tugagan namuna telefon, yopiq/bo‘sh parol/token
maydonlari ishlatiladi. Real CSV, ism, telefon, Telegram ID, token, parol yoki
capability havola screenshotlarda yo‘q. Har rasmda raqamlar screenshotdan
**oldin** DOM overlay sifatida render qilinadi; qo‘lda chizilgan UI emas.

Admin: 22 mavzu,21 screenshot (`group-form` yaratish/tahrirlashda bir xil formani
ko‘rsatadi va matnda farq tushuntirilgan). Public assets
`frontend/packages/ui/src/guide/images/`; bundler URLlarini hashli release
assetlariga aylantiradi. Capture manbasi:
`scripts/agent_skills/capture_admin_guide.cjs`, umumiy sintetik fixtures
`browser_fixtures.cjs`, markerlar `browser_helpers.cjs`. Qayta olish:

```sh
scripts/agent_skills/browser.sh scripts/agent_skills/capture_admin_guide.cjs
scripts/agent_skills/browser.sh scripts/agent_skills/browser_admin_guide.cjs
```

Capture private audit `.private/ui-acceptance/admin-guide-capture.json`ga
yoziladi. Testlar har grant/full-admin/superadmin/teacher/inactive/wildcard,
qidiruv, all-of grant, revoked mavzu/zoom va destinationni tekshiradi. Brauzer
barcha rasmlarni decode qiladi,22 mavzu, full-admin20 va limited6 mundarija,
1440/768/360px qidiruv/zoom/overflow va JS errorsni tekshiradi. Bu haqiqiy OTP
login yoki Telegramga yetkazish dalili sifatida ishlatilmaydi.

Qo‘llanma ishlashini tekshirishda ikki audit UI muammosi ham tuzatildi:
faqat attendance:read bilan oylik tarix selectorida groups:read so‘rovi talab
qilinmaydi; **Audit tarixi** tabida o‘sha read granti bilan sana/guruh bo‘yicha
immutable old/new/actor/role/time/reason ko‘rinadi. Guruh/sana almashsa oldingi
audit yopiladi, noto‘g‘ri dars natijasi ko‘rsatilmaydi.

Teacher: 11 mavzu va11 alohida teacher-portal screenshot. Kirish/OTP/session,
o‘z guruh/o‘quvchi/statistika, qoralama, yakunlash, darsdan keyingi2-kun
oxirigacha Toshkent vaqti bilan tuzatish, eski oy tarixi/audit, profil/rasm/parol
yo‘riqnomalari bor. Admin/superadmin hisobiga teacher qo‘llanmasi yopiq.
Portal wrapper va topic manbalari alohida; teacher bundle admin topiclarini
talab qilmaydi. PNG manzillarining pure URL konstruktorlari unused portal
assetlarini tree-shaking qilishga imkon beradi (final buildda tekshiriladi).

```sh
scripts/agent_skills/browser.sh scripts/agent_skills/capture_teacher_guide.cjs
scripts/agent_skills/browser.sh scripts/agent_skills/browser_teacher_guide.cjs
scripts/agent_skills/docker_env.sh node node /workspace/scripts/agent_skills/audit_guide_assets.cjs
```

Teacher va final UI/backend/release natijalari TASKS097–098da
alohida qayd qilinadi. Production faqat100–101 haqiqiy deploy qabuli bilan
tasdiqlanadi; local screenshot/test natijasi deploy muvaffaqiyati emas.
