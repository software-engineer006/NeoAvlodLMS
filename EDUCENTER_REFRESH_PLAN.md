# Educenter ma’lumotlarini yangilash

2026-yil sentyabr/oktyabr manbalari uchun foydalanuvchi development va
productionni yangilashni tasdiqladi. Xodimlar, loginlar, bot sozlamalari,
audit navbati/arxivlari/kalitlari va eski tarix dalillari saqlanadi.
Eski o‘quv dataset arxivlanadi; yangi dataset asosiy panellarda ko‘rinadi.
Immutable davomat auditi FKlari sababli eski yozuvlar TRUNCATE qilinmaydi.

## Tekshirilgan manbalar

| CSV guruhi | Qatorlar | Jadval, Toshkent vaqti | «k» belgisi |
| --- | ---: | --- | ---: |
| English Elementry&Beginer 1 | 10 | Dush/Chor/Jum, 09:00–10:30 | 22 |
| English Pre-intermediate 2 | 21 | Sesh/Pay/Shan, 15:00–16:30 | 71 |
| English Elementry&Beginer 3 | 27 | Sesh/Pay/Shan, 16:30–18:00 | 49 |
| Python&vibecoding 1 | 27 | Dush/Chor/Jum, 14:30–16:00 | 145 |
| Python&vibecoding 2 | 8 | Dush/Chor/Jum, 16:30–18:00 | 61 |
| Python&vibecoding 3 | 9 | Sesh/Pay/Shan, 09:30–11:00 | 22 |
| Python&vibecoding 4 | 15 | Sesh/Pay/Shan, 16:00–18:00 | 73 |

Python 4 vaqti CSVda ikki xil bo‘lgan; foydalanuvchi 16:00–18:00ni
to‘g‘ri vaqt sifatida tasdiqladi. Pythonning to‘rtta guruhi 217-xonaga
biriktiriladi. Asilaning guruhidagi aniq «k»lar ham qo‘shiladi.

117 qator 95 ta alohida ism-familiya va 116 ta guruhga biriktirishni beradi.
English 3 ichidagi takroriy qatorning daraja/izoh/manba ma’lumotlari
birlashtiriladi. Boshqa kurslarda qatnashayotgan o‘quvchi uchun alohida
profil yaratilmaydi. Ism-familiyaning manbadagi yozilishi va har qatorning
asl kataklari private provenance sifatida saqlanadi.

443 ta «k» o‘sha ustunning aniq sanasida kelganlik qoralamasiga o‘tadi.
Bo‘sh katak «kelmadi» deb hisoblanmaydi; import davomatni avtomatik
yakunlamaydi va ota-onaga xabar yubormaydi. Jadvaldan tashqari aniq source
sanasi ham o‘zboshimcha ko‘chirilmaydi. Kelajak sanasidagi belgi ham
source qoralamasi bo‘lib qoladi. Har o‘quvchi va guruhning jamisi footer
kontrol sonlariga tekshirilgan; noto‘g‘ri token yoki yangi sarlavha rad etiladi.

## Profil, guruh va oila

Bitta profil bir nechta guruhga StudentGroupEnrollment orqali ulanadi.
Sinf/maktab/telefon bir xil bo‘lsa profilga tushadi. Farqli qiymatlar
taxmin bilan tanlanmaydi: tasdiqlanmagan asosiy qiymat bo‘sh, barcha
variantlar private manbada saqlanadi, administrator ko‘rib tuzatadi.
Hozir 12 profilda manba tekshiruvi kerak: uchta telefon farqi, bitta sinf
farqi, bitta maktab farqi hamda noto‘g‘ri formatli telefonlar bor.

Daraja, MyGov holati va kurs izohi guruhga biriktirish kontekstida
saqlanadi. Beginner va Elementary bitta guruhda qoladi. MyGov manbada
status bo‘lib, login/parol emas; «o‘tdi», «o‘tmadi», «reyestrda yo‘q»/«r-y»,
«pullik», «qayta topshiradi», «yo‘q» va bo‘sh qiymat ma’nolari saqlanadi.

Telefonlar aralash ekanini foydalanuvchi tasdiqladi. Ular bolaga saqlanadi,
ota-ona phone asosida avtomatik yaratilmaydi yoki birlashtirilmaydi.
Administrator mavjud ota-onani tanlashi va bir nechta bolaga biriktirishi
mumkin. Bir ota-ona bitta Telegram bilan barcha bolalari uchun ism-familiya,
fan/guruh, sana, dars vaqti va holati aniq ko‘rsatilgan xabar oladi.
Teacher profilida faqat o‘zi o‘qitadigan guruh konteksti ochiladi.

## Xabar, ko‘chirish va audit

Xabar shabloni alohida admin ruxsati bilan tahrirlanadi, preview va
tekshiriladigan placeholders bo‘ladi. Xodim ID/rol/ismi server sessiyasi
va davomatning haqiqiy feedback muallifidan olinadi. Shablonning eski/yangi
qiymati, xodim va Toshkent vaqti auditga tushadi. Navbatdagi xabar matni va
shablon versiyasi snapshot bo‘ladi; shablon o‘zgarishi eski xabarni
o‘zboshimcha almashtirmaydi. Telegram uzunlik cheklovi boshqariladi.

Teacher yakunlash/tuzatish oqimi idempotent. Administrator va superadmin
davomatni tahrirlasa correction xabari yaratilmaydi; tegishli eski pending/
retry xabarlar ota-onaga noto‘g‘ri holatni yubormasligi uchun bekor qilinadi.
Worker va tahrir tranzaksiyasi delivery chegarasini lock orqali tartiblaydi.
Fake sender pending/processing/delivered/retry/shared-family holatlarini
tekshiradi. Productionda haqiqiy oilalarga test xabari yuborilmaydi.

Guruh ko‘chirish tanlangan membershipni almashtiradi; boshqa kurslar,
ota-ona, Telegram bog‘lanishi va eski davomat saqlanadi. Faol guruh/bo‘sh
joy/grant/duplicate/concurrency tekshiriladi; sabab va before/after auditda.

## Ikki bazani almashtirish tartibi

1. Barcha schema/API/UI va meaningful regressiyalar Dockerda tekshiriladi.
2. Private pg_dump, audit folder/key/config backup va restore rehearsal
   olinadi. Faol worker/yozuvlar maintenance/lock bilan boshqariladi.
3. Exact source SHA, foydalanuvchi qarorlari va dataset digest private
   approved manifest bilan mosligi tekshiriladi. Kirishlar va bot baseline
   olinadi; old source importer yangi formatni bexabar qo‘llamaydi.
4. Bitta transaction eski datasetni arxivlaydi va yangi current datasetni
   yaratadi. Source receipt qayta ishga tushirishda duplicate yaratmaydi.
   Xodim/credential/audit o‘chirilmaydi, source k importi notification yaratmaydi.
5. 95 profil/116 membership/7 guruh/443 mark/all metadata va 217-xona,
   staff/login/bot/audit saqlanishi reconciled tekshiriladi.
6. Professional push va exact-SHA green CI/CD, TLS asset hashes,
   portal UI/RBAC/guide/fake delivery hamda API/worker/archive health
   bilan production qabuli tasdiqlanadi.

Raw CSV, pupil/contact/provenance/manifest va secretlar Gitga kiritilmaydi.
Public testlar faqat sintetik odamlar va xabarlar bilan ishlaydi.

Private deployment manbasi `$APP_ROOT/private/educenter-refresh-data/` ichida
aynan yettita CSV va tasdiqlangan `plan.sha256` bo‘ladi. `dataset_refresh`
CLI avval dry-run, keyin `--apply` bilan ishlaydi; digest o‘zgarsa rad etadi.
`--validate-only` source/digestni DBga ulanmasdan tekshiradi; deployment buni
API/worker to‘xtashidan oldin bajaradi. Import fayl egasi UID/GIDsi bilan,
read-only source mountda ishlaydi; private papka/fayl 0700/0600 qoladi.
Arxivga faqat yettita CSV va digestni kiriting; macOS `._` yordamchi fayllari
qat’iy parser tomonidan ortiqcha source sifatida rad etiladi.
Receipt takroriy deployda admin tuzatishlarini qayta yozmaydi. Eski datasetdagi
yuborilmagan davomat/broadcast xabarlari bekor qilinadi; yangi import xabar
navbati yoki yakunlangan dars yaratmaydi. Eski capability havolalari ishlamaydi.

0017 migratsiyasi business jadvallariga arxiv chegarasini qo‘shadi. Joriy
ORM so‘rovlari, join/alias/lookup va ID orqali o‘zgartirishlarda eski satrlar
yashiriladi; audit schema va AttendanceChange yozuvlari saqlanadi. Importdan
keyin `$APP_ROOT/.dataset-enforced` eski, arxiv filtrisiz runtimega rollbackni
rad etadi. Xatoda xavfsiz runtime bilan fix-forward yoki audit/keyni saqlaydigan
private backup restore kerak; eski kod bilan barcha datasetni ochish mumkin emas.
