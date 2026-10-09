# Python dasturlash&vibecoding import rejasi — 2026-10-09

Asosiy bajarish reestri va dalillar: [TASKS.md](TASKS.md), 076–080.
Mavjud kod va haqiqiy hisoblar saqlanadi. Xom CSV, parol, token va shaxsiy
auditlar Gitga kiritilmaydi. Barcha runtime tekshiruvlari Dockerda.

1. **076 — Audit.** `educenter_data`dagi to‘rtta CSVning sarlavhalari,
   o‘quvchilar, kontaktlar, izohlar va sanalarini tekshirish; SHA256 va private
   audit saqlash. Sana bo‘lmagan ustunlar davomat sifatida olinmaydi.
2. **077 — Import.** Superadmin va mavjud Jasur/Dilmurod hisoblarini tekshirish;
   bitta `Python dasturlash&vibecoding` fani, to‘rtta guruh va barcha haqiqiy
   o‘quvchilarni bog‘laydigan dry-run/apply CLI. Birinchi ikki guruh Jasur:
   Dush/Chor/Juma 14:30–16:00 va 16:30–18:00; keyingi ikki guruh Dilmurod:
   Sesh/Pay/Shanba 09:30–11:00 va 16:00–18:00. `k` — keldi, bo‘sh dars
   katagi — kelmadi. Import atomik va takroriy ishga tushirish xavfsiz.
3. **078 — Local apply.** Xizmat qilayotgan DB backup/restore tekshiruvi,
   eski Python guruhlariga manba bo‘yicha moslashtirish (dublikat yaratmaslik),
   dry-run hash bilan apply, qayta apply va API/ownership/statistika tekshiruvi.
4. **079 — Deploy.** Private data serverda alohida katalogda; migratsiyadan
   keyin mavjud CI/CD orqali bir xil idempotent import. Xato bo‘lsa deploy
   to‘xtaydi; katalog berilmasa mavjud odatiy deploy ishlaydi. CI sintetik
   ma’lumot bilan tekshiradi, production PII/secret Gitda saqlanmaydi.
5. **080 — Yakuniy qabul.** Docker backend/frontend/migration/agent checks,
   deploy regressiyasi, local portal smoke; foydalanuvchiga aniq sonlar,
   portal manzillari va private hisob/import qo‘llanmasini berish.

## Bajarilgan natija

076–080 yakunlandi; to‘liq dalillar TASKS.mdda. Local Dockerda bitta fan,
CSV nomiga teng 4 guruh, 62 o‘quvchi va 364 davomat yozuvi mavjud.
3-guruh «23» ustuni foydalanuvchi ko‘rsatmasiga ko‘ra chiqarilgan; 4 noaniq
katak manba izohida saqlanadi. Qayta import 0 yangi yozuv beradi.
225 backend va 122 frontend testi, migratsiya, lint/typecheck, release checksum,
11 deploy regressiyasi va production Docker import/TLS/rollback tekshirildi.
Serverga uzatish uchun private paket tayyor; haqiqiy Git push/VPS deploy
bajarilmagan. Tartib: EDUCENTER_IMPORT.md.
