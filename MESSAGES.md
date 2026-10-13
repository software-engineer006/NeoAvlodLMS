# Administrator Telegram xabarlari

Admin paneldagi **Xabarlar** bo‘limi `messages:send` ruxsatiga ega faol
administratorlarga va superadminga ochiq. Teacher portalida bu amal mavjud emas.
0009 migratsiyasi mavjud administratorlarga ruxsat beradi; keyingi xodimlarda
superadmin uni xodim formasidan belgilaydi.

1. Ota-onalar, o‘quvchilar yoki ikkalasini tanlang.
2. **Tanlanganlar** orqali ism, farzand, guruh va ulanish holati bilan qidiring.
   Tanlov sahifalar almashganda saqlanadi. **Guruhlar bo‘yicha** bir yoki bir
   nechta guruhni, **Barchaga** esa faol guruhlardagi barcha tegishli hisoblarni
   qamrab oladi. Faol farzandi bo‘lmagan ota-ona tanlovga kirmaydi.
3. Sarlavha va matnni yozing yoki tahrirlanuvchi namunadan boshlang. Markaz nomi,
   sarlavha va matn umumiy 4096 limitga kiradi. Matn oddiy matn sifatida yuboriladi.
4. Qabul qiluvchilarni ko‘rib chiqing. Ulanmagan va bir xil Telegram hisoblari
   soni ko‘rsatiladi; bitta chatga bitta xabar yuboriladi.
5. Yuborishni tasdiqlang va navbatga qo‘shing. Matn yoki tanlov o‘zgarsa qayta
   ko‘rib chiqish talab qilinadi. Server ro‘yxati o‘zgarganda ham qayta preview
   kerak. Tarmoq xatosidan keyin ayni yuborishni qayta urinish dublikat kampaniya
   yaratmaydi.
6. **Yuborishlar tarixi** orqali yuboruvchi, vaqt, matn, auditoriya va har bir
   qabul qiluvchining holatini ko‘ring. Xatoli yuborishlarni qayta urinish faqat
   xatolilarni navbatga qaytaradi; to‘xtatish faqat qolgan navbatni bekor qiladi.
   Yetkazilgan xabarlar qayta yuborilmaydi yoki Telegramdan o‘chirilmaydi.

“Yetkazildi” Telegram xabarni qabul qilganini bildiradi; o‘qilganini aniqlamaydi.
Botga ulanish uchun o‘quvchi/ota-ona profilidagi amaldagi havolani ochib Start
bosish kerak. Boshqa botga o‘tilganda qayta ulanishgacha yetkazish kutadi.

Navbat DBda saqlanadi. API tezkor dispatchni boshlaydi; alohida worker qolgan
navbatni va retrylarni restartdan keyin davom ettiradi. Yuborish paytida xodim
ruxsati/statusi, qabul qiluvchining faolligi, guruh a’zoligi va joriy ulanishi
yana tekshiriladi. Bot tokeni, Telegram ID va capability UUID frontenddagi
ro‘yxat/preview/tarix javoblariga kiritilmaydi.

Global broadcast tezligi 10/soniya, bir chatga kamida bir soniya; 429 javobidagi
`retry_after` barcha shu bot navbatlari uchun saqlanadi. Vaqtinchalik xatolar
besh urinishdan keyin xatoli holatga o‘tadi. Bloklangan chat kabi doimiy xatolar
avtomatik takrorlanmaydi. Telegram bilan aloqa uzilib, tashqi qabul javobi
yo‘qolsa at-least-once yetkazishda dublikat ehtimoli mavjud.
Telegram chegaralari: [sendMessage](https://core.telegram.org/bots/api#sendmessage),
[broadcast tezligi](https://core.telegram.org/bots/faq#how-can-i-message-all-of-my-bot-39s-subscribers-at-once).

Docker sinovlari sintetik Telegram transporti va disposable test DBda bajariladi.
Brauzer sinovi haqiqiy app komponentlarini sintetik API javoblari bilan
1440/768/360pxda ochadi; haqiqiy oilalarga xabar yubormaydi.

Local qabul (2026-10-13): private backup/restore bir xil count berdi; 0009
head/model mos. Serving bazada 6 xodim, 7 guruh, 118 o‘quvchi, 462 davomat
yozuvi saqlangan. Read-only audience API: 0 ota-ona, 118 o‘quvchi, barchasi
hozircha ulanmagan; 0 kampaniya va 0 delivery. English importning barcha
oldingi row/credential digestlari tekshirildi; 0009ning aniq `messages:send`
admin granti alohida ruxsat etilgan yagona o‘zgarish. Local worker haqiqiy
production bot pollingiga xalaqit bermasligi uchun to‘xtagan. Production
deployment 099–101 vazifalarning alohida acceptance natijasi bilan qayd qilinadi.
