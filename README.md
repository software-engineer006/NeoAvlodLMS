# NeoAvlodLMS

NeoAvlod uchun to‘liq LMS platformasi. Tizim arxitekturasi, modellar, auth, Telegram bot
va frontend boshqaruv panellari to‘liq ishlab chiqilgan. Ishlab chiqarish (production)
muhitiga joylashtirish yo‘riqnomasi [DEPLOYMENT.md](DEPLOYMENT.md) faylida, vazifalar
ro‘yxati va qabul dalillari [TASKS.md](TASKS.md) da saqlanadi.

Docker Desktop yoki Docker Engine va Compose kerak. Python/Node hostga
o‘rnatilmaydi. Loyiha ildizidan:

```bash
scripts/agent_skills/docker_env.sh up
scripts/agent_skills/check_backend.sh
scripts/agent_skills/docker_env.sh smoke
```

Compose local `.env` fayliga random DB secretni avtomatik yozadi; u Gitga
kirmaydi. PostgreSQL image `postgres:18.6`; ma’lumotlar named volumeda,
test database esa alohida disposable konteynerda saqlanadi.
Server `127.0.0.1:8000` da, process health `/api/v1/health` da,
development API hujjatlari `/api/v1/docs` da ochiladi. Health hozir faqat
API jarayonini tekshiradi; `/api/v1/ready` PostgreSQL ulanishini tekshiradi.

Agent skriptlari:

```bash
scripts/agent_skills/check_agent_skills.sh
scripts/agent_skills/task.sh next
scripts/agent_skills/task.sh resume
scripts/agent_skills/check_frontend.sh
scripts/agent_skills/run_migrations.sh
```

Frontend va migratsiya skriptlari tegishli vazifalar yaratilmaguncha xato
qaytaradi. Migratsiya skripti sozlangan bazani yangilaydi; development yoki
deployment uchun tanlangan database konfiguratsiyasini oldindan tekshiring.

Boshqa AI agentga `TASKS.md buni bajar` deyish yetarli: [AGENTS.md](AGENTS.md)
[resume skillini](skills/neoavlod-resume/SKILL.md) o‘qishni va bitta faol
vazifani Dockerda yakunlab keyingisiga o‘tishni belgilaydi. To‘xtatish:
`scripts/agent_skills/docker_env.sh stop`; bu database volume’ni o‘chirmaydi.

Migratsiyadan keyin birinchi superadminni yaratish (parol yashirin so‘raladi):

```bash
scripts/agent_skills/run_migrations.sh
scripts/agent_skills/docker_env.sh bootstrap --username owner --phone +998901234567 --first-name Ali --last-name Vali
```

Standart parol mavjud emas. Takroriy bootstrap mavjud superadmin parolini
o‘zgartirmaydi. Boshlang‘ich bot sozlamalari qo‘shilgach CLI bergan
`staff_<uuid>` payload orqali Telegram ulanadi va web login OTP ishlaydi.
