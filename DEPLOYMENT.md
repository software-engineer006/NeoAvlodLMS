# NeoAvlod LMS — Ubuntu Production Deployment Guide

Ushbu qo‘llanma **NeoAvlod LMS** tizimini Ubuntu 22.04/24.04 LTS serverida to‘liq xavfsiz, yuqori unumdorlikka ega va barqaror ishlab chiqarish (production) muhitiga joylashtirish bo‘yicha to‘liq yo‘riqnomani taqdim etadi.

---

## 1. Arxitektura va server talablari

- **Operatsion tizim**: Ubuntu 22.04 LTS yoki 24.04 LTS (x86_64)
- **Minimal resurslar**: 2 vCPU, 4 GB RAM, 40 GB NVMe SSD
- **Dasturiy ta’minot**:
  - Docker Engine 26+ va Docker Compose v2
  - Nginx (Reverse proxy, TLS termination, statik fayllar)
  - Certbot (Let's Encrypt SSL/TLS sertifikatlari)
  - PostgreSQL 18.6 (Docker konteyneri orqali, persistent volume)
  - Python 3.13 (Docker multi-stage runtime, nonroot `app` foydalanuvchisi)

---

## 2. DNS va subdomenlar konfiguratsiyasi

DNS provayderingizda (masalan, Cloudflare, Namecheap) quyidagi `A` yozuvlarini serveringizning tashqi IP manziliga yo‘naltiring:

| Subdomen | Yozuv turi | Nishon (Target) | Vazifasi |
|---|---|---|---|
| `admin.eduneo.uz` | `A` | `<SERVER_IP>` | Admin va Rahbariyat SPA portali |
| `teacher.eduneo.uz` | `A` | `<SERVER_IP>` | O‘qituvchilar SPA portali |
| `api.eduneo.uz` | `A` | `<SERVER_IP>` | Backend REST API xizmati |

---

## 3. Serverni tayyorlash va paketlarni o‘rnatish

Serverga SSH orqali kiring va tizimni yangilang:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git nginx certbot python3-certbot-nginx ca-certificates ufw
```

### Docker Engine va Docker Compose o‘rnatish:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### UFW Brandmauer (Firewall) sozlash:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 4. Loyiha kataloglari va fayl ruxsatlari

Serverda deployment uchun standart kataloglar strukturasini yarating:

```bash
# Veb statik fayllar uchun
sudo mkdir -p /var/www/neoavlod/releases
sudo mkdir -p /var/www/certbot

# Ilova va docker konfiguratsiyasi uchun
sudo mkdir -p /opt/neoavlod/releases
sudo mkdir -p /opt/neoavlod/scripts
sudo mkdir -p /var/backups/neoavlod

# Foydalanuvchi ruxsatlari
sudo chown -R $USER:$USER /opt/neoavlod
sudo chown -R $USER:$USER /var/www/neoavlod
```

---

## 5. SSL/TLS sertifikatlarini olish (Certbot)

Nginx konfiguratsiyasidan oldin ACME challenge orqali sertifikat oling:

```bash
sudo certbot certonly --standalone \
  -d admin.eduneo.uz \
  -d teacher.eduneo.uz \
  -d api.eduneo.uz \
  --email admin@eduneo.uz \
  --agree-tos \
  --no-eff-email
```

*Eslatma*: Agar har bir subdomen alohida sertifikat olgan bo‘lsa yoki wildcard bo‘lsa, Nginx konfiguratsiyasida mos yo‘llar ko‘rsatiladi.

Avtomatik yangilanishni tekshirish:
```bash
sudo certbot renew --dry-run
```

---

## 6. Nginx konfiguratsiyasi

Loyiha repozitoriysidagi Nginx fayllarini serverga joylashtiring:

```bash
sudo cp -r nginx/snippets /etc/nginx/
sudo cp nginx/conf.d/eduneo.conf /etc/nginx/conf.d/eduneo.conf
```

Sintaksisni tekshirish va Nginx-ni qayta yuklash:
```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl enable nginx
```

---

## 7. Production muhiti o‘zgaruvchilari (`.env.production`)

`/opt/neoavlod/.env.production` faylini yarating va faqat `root` yoki ilova foydalanuvchisiga ruxsat bering (`chmod 600`):

```bash
sudo touch /opt/neoavlod/.env.production
sudo chmod 600 /opt/neoavlod/.env.production
```

Fayl tarkibini quyidagicha to‘ldiring:

```ini
# PostgreSQL 18.6 ma'lumotlar bazasi
POSTGRES_USER=neoavlod
POSTGRES_DB=neoavlod
POSTGRES_PASSWORD=BU_YERGA_KUCHLI_PAROL_YOZING

# Backend porti (faqat localhost 127.0.0.1 ga bog'lanadi)
API_PORT=8000

# NeoAvlod ilovasi
NEOAVLOD_ENVIRONMENT=production
NEOAVLOD_DEBUG=false
NEOAVLOD_DATABASE_URL=postgresql+asyncpg://neoavlod:BU_YERGA_KUCHLI_PAROL_YOZING@database:5432/neoavlod

# Xavfsizlik kaliti (HMAC, CSRF va OTP uchun)
# Yaratish: openssl rand -hex 32
NEOAVLOD_SECURITY_SECRET=BU_YERGA_HEX_32_BELGILI_MAXFIY_KALIT

# Telegram bot shifrlash kaliti (Fernet formati)
# Yaratish: python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
NEOAVLOD_BOT_ENCRYPTION_KEY=BU_YERGA_FERNET_BASE64_KALIT

# Portal domenlari (qat'iy HTTPS)
NEOAVLOD_ADMIN_ORIGIN=https://admin.eduneo.uz
NEOAVLOD_TEACHER_ORIGIN=https://teacher.eduneo.uz
```

---

## 8. Docker konteynerlarini ishga tushirish va migratsiyalar

`/opt/neoavlod/` katalogida `compose.prod.yaml` mavjud bo‘lishini ta’minlang.

1. **Ma’lumotlar bazasini ishga tushirish**:
   ```bash
   cd /opt/neoavlod
   docker compose -f compose.prod.yaml --env-file .env.production up -d --wait database
   ```

2. **Alembic ma’lumotlar bazasi migratsiyalarini o‘tkazish**:
   ```bash
   docker compose -f compose.prod.yaml --env-file .env.production run --rm migrations
   ```

3. **API va Telegram Worker Singleton-ni ishga tushirish**:
   ```bash
   docker compose -f compose.prod.yaml --env-file .env.production up -d --wait api worker
   ```

4. **Holatni tekshirish**:
   ```bash
   docker compose -f compose.prod.yaml --env-file .env.production ps
   curl -s http://127.0.0.1:8000/api/v1/health
   curl -s http://127.0.0.1:8000/api/v1/ready
   ```

---

## 9. Superadminni bootstrap qilish (Boshlang‘ich hisob yaratish)

Tizimda boshlang‘ich default parol mavjud emas. Superadmin hisobi buyruqlar satri orqali maxfiy kiritiladi:

```bash
docker compose -f compose.prod.yaml --env-file .env.production run --rm api \
  python -m neoavlod.cli bootstrap \
    --username superadmin \
    --phone "+998901234567" \
    --first-name Asosiy \
    --last-name Admin \
    --password-stdin
```

Terminalda superadmin parolini kiritib `Enter` bosing.

---

## 10. Telegram Bot tokenini kiritish va ishga tushirish

Telegram boti tokenni server CLI orqali xavfsiz o‘rnatish:

```bash
docker compose -f compose.prod.yaml --env-file .env.production run --rm api \
  python -m neoavlod.cli set-bot-token --token-stdin
```

Yoki superadmin login qilib, `https://admin.eduneo.uz` boshqaruv paneli orqali **Bot sozlamalari** bo‘limiga kirib kiritishi mumkin.

---

## 11. GitHub Actions CI/CD sirlarini sozlash

GitHub repozitoriyasining `Settings -> Secrets and variables -> Actions` bo‘limida quyidagi maxfiy o‘zgaruvchilarni kiriting:

| Secret nomi | Tavsifi | Namuna |
|---|---|---|
| `SSH_HOST` | Serverning IP manzili | `198.51.100.25` |
| `SSH_USER` | Serverdagi foydalanuvchi nomi | `deploy` yoki `ubuntu` |
| `SSH_PRIVATE_KEY` | SSH shaxsiy kaliti | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `SSH_PORT` | SSH porti | `22` |
| `SSH_KNOWN_HOSTS` | Pinned host fingerprinti (`ssh-keyscan -H <IP>`) | `198.51.100.25 ssh-ed25519 AAAAC3Nza...` |

---

## 12. Ma’lumotlar bazasini zaxiralash (Backup) va tiklash (Restore)

### Kunlik avtomatik zaxiralash skripti:

`/opt/neoavlod/scripts/backup.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="/var/backups/neoavlod"
mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$BACKUP_DIR/db_$TIMESTAMP.dump"

cd /opt/neoavlod
docker compose -f compose.prod.yaml --env-file .env.production exec -T database \
  pg_dump -U neoavlod -d neoavlod -Fc > "$FILE"

# 14 kundan eski zaxiralarni tozalash
find "$BACKUP_DIR" -type f -name "db_*.dump" -mtime +14 -delete
printf 'Zaxira nusxa yaratildi: %s\n' "$FILE"
```

Cron vazifasini qo‘shish (`crontab -e`):
```cron
0 3 * * * /opt/neoavlod/scripts/backup.sh >> /var/log/neoavlod_backup.log 2>&1
```

### Zaxiradan tiklash (Restore):

```bash
cd /opt/neoavlod
BACKUP_FILE="/var/backups/neoavlod/db_20261005_030000.dump"

# Ma'lumotlar bazasini tozalab tiklash
docker compose -f compose.prod.yaml --env-file .env.production exec -T database \
  pg_restore -U neoavlod -d neoavlod --clean "$BACKUP_FILE"
```

---

## 13. Release Rollback (Orqaga qaytarish) jarayoni

### Avtomatik Rollback:
Agar yangi release o‘rnatilganda post-deployment health check (`/api/v1/health` va `/api/v1/ready`) 20 soniya ichida javob bermasa, `deploy.sh` skripti avtomatik tarzda `rollback.sh` skriptini chaqiradi va tizim avvalgi ishchi release holatiga qaytariladi.

### Qo‘lda Rollback qilish:
Serverda istalgan paytda orqaga qaytish uchun:
```bash
sudo /opt/neoavlod/scripts/rollback.sh
```

Yoki GitHub Actions interfeysida:
`Actions -> CI/CD Pipeline & Rollback -> Run workflow` tugmasini bosib, `action: rollback` parametrini tanlang.

---

## 14. Yakuniy biznes-oqim qabul tekshiruvi (Checklist)

Tizim to‘liq topshirilishidan oldin quyidagi tekshiruvlar ro‘yxati bajarilishi shart:

- [ ] **1. DNS va SSL tekshiruvi**:
  - `https://admin.eduneo.uz`, `https://teacher.eduneo.uz` va `https://api.eduneo.uz` yashil qulf belgisi bilan ochilishi.
  - HTTP dan HTTPS ga 301 yo‘naltirilishi.
- [ ] **2. Superadmin autentifikatsiyasi**:
  - `superadmin` hisobi bilan login qilish.
  - Telegram orqali 6 raqamli bir martalik OTP kodini qabul qilish va panelga kirish.
- [ ] **3. Bot sozlamalari va Telegram ulanishi**:
  - Bot tokeni kiritilishi va getMe orqali bot username tasdiqlanishi.
  - Bot worker yangilangan tokenni avtomatik yuklashi (hot reload).
- [ ] **4. O‘qituvchi yaratish va hisob bog‘lash**:
  - Xodimlar bo‘limida yangi o‘qituvchi qo‘shish.
  - Deep link orqali Telegram botga `/start staff_<UUID>` yuborib hisobni bog‘lash.
- [ ] **5. Fan va Guruh yaratish**:
  - Yangi fan yaratish.
  - Dars kunlari, vaqti, narxi va sig‘imi (capacity) ko‘rsatilgan yangi guruh ochish va unga o‘qituvchini biriktirish.
- [ ] **6. O‘quvchi va Ota-onani ro‘yxatga olish**:
  - Yagona formadan o‘quvchi va ota-onani guruhga qo‘shish.
  - Ota-ona telefoniga berilgan deep link orqali Telegram botga `/start parent_<UUID>` yuborish.
- [ ] **7. O‘qituvchi portali (`teacher.eduneo.uz`)**:
  - O‘qituvchi paroli va Telegram OTP orqali tizimga kirishi.
  - Faqat o‘ziga biriktirilgan guruhlarni ko‘rishi.
- [ ] **8. Davomat olish va bildirishnoma yuborish**:
  - O‘qituvchi guruh davomatini (Bor, Yo‘q, Kechikdi va izoh) belgilashi.
  - Davomatni yakunlashi (Finalize).
  - Outbox worker orqali ota-onaning Telegramiga o‘zbek tilidagi rasmiy xabarnoma yetib borishi.
- [ ] **9. Admin nazorati**:
  - Admin panelida davomat tarixi, statistika va filtrlar to‘g‘ri aks etishi.
- [ ] **10. Xavfsizlik va ruxsatlar izolyatsiyasi**:
  - O‘qituvchi admin paneliga kirganda 403 Forbidden ko‘rinishi.
  - Admin o‘qituvchi sahifalariga kirganda 403 Forbidden ko‘rinishi.
  - Parol o‘zgartirilganda barcha eski sessiyalar bekor qilinishi.
