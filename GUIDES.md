# React portal qo‘llanmalari

Qo‘llanma rastr screenshot o‘rniga typed React namuna ekranlarini ko‘rsatadi.
`guide/scenes/GuidePreview.tsx` yagona renderer; forma, jadval, badge, tugma va
ko‘rsatkichlar amaldagi shared UI atomlaridan quriladi. Tailwind4.3.3 container
queries namunaning o‘z kengligiga mos layout beradi. Matn va SVG kattalashtirilganda
tiniq qoladi. Admin/teacher registries umumiy login/profil/tarix namunalari va
formalarni qayta ishlatadi; live management komponentlari import qilinmaydi.

Admin/superadmin uchun23 mavzu; barcha ruxsatli administrator19 mavzuni ko‘radi.
Ruxsatlar, bot, davomat auditi va kunlik loglar faqat superadmin uchun. Bu
administrator permission katalogiga log ruxsatini qo‘shmaydi. Student statistikasi
students:read va attendance:read birga bo‘lganda chiqadi. Ruxsat bekor qilinsa
mavzu va kattalashtirilgan namuna darhol yopiladi.

Teacher uchun10 mavzu: kirish/3-minut OTP/7-kun sessiya, o‘z guruh va o‘quvchilari,
qoralama, yakunlash, ikki kun ichidagi sababli tuzatish, oylik tarix, profil va
parol. Teacher auditni ko‘rmaydi; odatiy davomat tarixi/statistikasi ishlaydi.
Mavjud status/izohni tahrirlash barcha rollarda sabab talab qiladi. Birinchi
belgilash, no-op va o‘zgarishsiz yakunlash sabab talab qilmaydi.

Har bir namuna regioni matnli qadam raqamiga mos. Preview subtree native `inert`,
`aria-hidden`, `tabIndex=-1` va readonly qiymatlarga ega; mustaqil `role=img`
tavsifi va tashqi matnli qadamlar screen reader uchun qoladi. Preview form
submit, API/network, saqlash, Telegram yuborish yoki credential o‘qishni bajarmaydi.
Faqat «Namuna» ma’lumotlar ishlatiladi; parol/token/kod maydonlari bo‘sh.

Qidiruv, mundarija, bo‘lim filtri, oldingi/keyingi mavzu, «Tushundim», zoom va
ruxsatli bo‘limga o‘tish saqlangan. O‘rganilgan mavzular faqat shu ochiq
qo‘llanmaning xotirasida; shaxsiy loglar browser storagega yozilmaydi.

Superadmin «Kunlik loglarni ko‘rish va yuklab olish» mavzusidan kun tanlash,
xodim/amal/natija filtri, aniq vaqt/old-new/sabab, `.jsonl.gz` eksport va
o‘chirish/tahrirlashning yo‘qligini o‘rganadi. Kunlik eksport filtrga qaramay
tanlangan kunning barcha yozuvlarini beradi. Infra chegarasi va backup/kalit
operatsiyalari AUDIT_PLAN.md va audit operatsion qo‘llanmasida.

Docker tekshiruvlari:

```sh
scripts/agent_skills/check_frontend.sh
scripts/agent_skills/docker_env.sh node npm test -- --run packages/ui/src/guide/__tests__
scripts/agent_skills/docker_env.sh node node /workspace/scripts/agent_skills/audit_guide_assets.cjs
scripts/agent_skills/browser.sh scripts/agent_skills/browser_admin_guide.cjs
scripts/agent_skills/browser.sh scripts/agent_skills/browser_teacher_guide.cjs
```

Brauzer barcha API so‘rovlarini yopiq sintetik fixtures bilan tutadi. Noma’lum
endpoint403 va test failure; live backendga fallback yoki haqiqiy Telegram xabari
yo‘q. UI acceptance rasmlari faqat `.private/ui-acceptance/`ga saqlanadi va
ilovaning public qo‘llanmasiga bundlanmaydi. Eski capture commandlar shu yangi
acceptance tekshiruvlariga yo‘naltiriladi;32 public PNG manbasi olib tashlangan.
