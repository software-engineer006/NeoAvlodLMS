# Lokal portallar — haqiqiy ma’lumotlar

Docker Desktop ishlayotganida:

```bash
scripts/agent_skills/local_demo.sh up
```

| Portal | Manzil | Username |
|---|---|---|
| Superadmin | http://localhost:3000 | ceo_mohira |
| O‘qituvchi | http://127.0.0.1:3001 | teacher_dilmurod |

Parol va shaxsiy Telegram /start havolalari `.private/real-data/HISOBLAR.md`
owner-only faylida. Har bir havolani faqat tegishli hisob egasi ochadi.
Botda Start bosilgach haqiqiy Telegram ID saqlanadi. Username/paroldan so‘ng
Telegramga yuborilgan 6 xonali kod bilan kiriladi; kod 5 daqiqa va bir martalik.
Birinchi kirishda generated vaqtinchalik parol yangilanadi.

Portallarni jadvaldagi hostlarda oching: cookie ikki portal orasida aralashmaydi.
Tarixiy `neoavlod_demo` nomli alohida persistent bazada endi haqiqiy roster mavjud:
2 fan, 10 guruh, 81 enrollment va 4 xodim. Sinov hisoblari/guruhlar tozalangan.
Demo seed o‘chirilgan; `up` va restart haqiqiy yozuvlarni saqlaydi.
Smoke faqat read-only: hech qanday Telegram ID yoki OTP uydirib kiritmaydi.
Import/karantin va backup tafsilotlari: `REAL_DATA_IMPORT.md` va `TASKS.md`.

```bash
scripts/agent_skills/local_demo.sh status
scripts/agent_skills/local_demo.sh smoke
scripts/agent_skills/local_demo.sh stop
```
