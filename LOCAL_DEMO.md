# Local frontend sinovi

Docker Desktop ishlayotganida:

```bash
scripts/agent_skills/local_demo.sh up
```

| Portal | Manzil | Login | Parol |
|---|---|---|---|
| Superadmin | http://localhost:3000 | superadmin | 1234 |
| Teacher | http://127.0.0.1:3001 | teacher | 1234 |

Login so‘ng local tasdiqlash kodi ekranda chiqadi; uni OTP maydoniga kiriting.
Kod tasodifiy, 5 daqiqa amal qiladi va bir marta ishlatiladi. Telegramga haqiqiy
xabar yuborilmaydi. Teacher uchun demo guruh va 3 talaba mavjud.

Portallarni jadvaldagi hostlarda oching: cookie ikki portal orasida aralashmaydi.
Sinov hisoblari `neoavlod_demo` bazasida, alohida persistent Docker volume ichida.
Qayta `up` mavjud hisoblar, parollar va sinovda kiritilgan ma’lumotlarni saqlaydi.
Parol o‘zgartirishda ilovaning odatiy kuchli parol talabi amal qiladi.
Production `neoavlod.main:create_app` local OTP endpointni ro‘yxatdan o‘tkazmaydi.

```bash
scripts/agent_skills/local_demo.sh status
scripts/agent_skills/local_demo.sh smoke
scripts/agent_skills/local_demo.sh stop
```
