# NeoAvlodLMS — Ubuntu serverga deployment

Ushbu tartib Ubuntu 22.04/24.04, `root` SSH sessiyasi va
`git@github.com:software-engineer006/NeoAvlodLMS.git` uchun yozilgan.
Buyruq bloklari qaysi kompyuterda bajarilishi alohida ko‘rsatilgan.
VPS manzili: `189.74.99.79`, SSH foydalanuvchisi: `root`.
SSH porti boshqacha bo‘lsa va telefon raqami kiritiladigan joylarda o‘zingiznikini yozing.

Oqim: kompyuterda Docker frontend build → build va kodni Gitga commit/push →
Actions Docker testlari → serverdagi aniq commit → yangi backend image +
frontend fayllari → backup/migration → health va HTTPS tekshiruv → release faollashadi.
CI buildni qayta yaratib, kompyuteringizda tayyorlangan build bilan solishtiradi;
server tayyor statik fayllarni tarqatadi va backend image’ini o‘zi build qiladi.

| Nima | Joylashuvi |
|---|---|
| Server Git clone | `/root/NeoAvlodLMS` |
| Maxfiy production env | `/opt/neoavlod/.env.production` |
| O‘zgarmas kod releaselari | `/opt/neoavlod/releases/<40-belgili-SHA>` |
| Joriy kodga havola | `/opt/neoavlod/current` |
| Frontend releaselari | `/var/www/neoavlod/releases/<SHA>/admin`, `teacher` |
| Nginx frontend ildizlari | `/var/www/neoavlod/admin`, `/var/www/neoavlod/teacher` |
| Backend | `127.0.0.1:8000` → `api.eduneo.uz` va portal `/api/` proxy |
| Doimiy PostgreSQL volume | `neoavlod-prod_postgres-data` |
| Doimiy Media volume | `neoavlod-prod_media-data` (`/app/media`) |
| Backup | `/var/backups/neoavlod/*.dump` va media fayllari |

Serverdagi clone bilan production release alohida. Deploy `git pull/reset` bilan
qo‘lda o‘zgartirilgan fayllarni o‘chirmaydi; `git fetch` va `git archive` ishlatadi.
Production uchun local demo hisoblari/bazasi ishlatilmaydi.

## 1. Kompyuteringizda yangi deployment fayllarini Gitga tayyorlash

Docker Desktop ishlayotgan bo‘lsin. Loyiha katalogida:

```bash
cd /Users/dulmurod/NeoAvlodLMS
scripts/deploy/build_frontend.sh

git status --short
git add backend frontend scripts nginx .github compose.prod.yaml DEPLOYMENT.md TASKS.md LOCAL_DEMO.md compose.local.yaml
# Tahrirlangan boshqa kerakli fayllarni ham git add bilan kiriting.
git diff --cached --stat
git commit -m "Fix Ubuntu deployment and verify committed frontend releases"
git push origin main
```

`frontend/release/` — Gitga kiritiladigan production build.
`frontend/apps/*/dist` va `node_modules` Gitga kiritilmaydi.
Build skripti Dockerda install, typecheck, lint, test va build bajaradi.
Frontend `.env*` fayllari bo‘lsa build to‘xtaydi: production bundle lokal
sozlamalarga bog‘lanmasligi kerak. Maxfiy kalitlar frontendga yozilmaydi.

Birinchi push paytida VPS/Actions secrets hali tayyor bo‘lmasa deploy job xato
berishi mumkin. Quyidagi server sozlashni tugatib, 9-qadamda workflow’ni qayta
ishga tushiring. Test xatolarini esa avval tuzating.

## 2. Server: paketlar va Docker

Server konsolida yoki `ssh root@189.74.99.79` orqali:

```bash
apt update
apt install -y git openssh-client curl ca-certificates nginx certbot openssl dnsutils ufw util-linux
systemctl enable --now nginx
```

Docker mavjud bo‘lsa `docker version` va `docker compose version` ni tekshiring.
Rasmiy Docker Engine/Compose hali o‘rnatilmagan bo‘lsa:

```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

cat > /etc/apt/sources.list.d/docker.sources <<EOF_DOCKER
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && printf '%s' "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF_DOCKER

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker version
docker compose version
```

Mavjud eski `docker.io`/`containerd` paketlari bilan konflikt bo‘lsa, amaldagi
containerlarni rejalashtirib, [rasmiy Ubuntu o‘rnatish yo‘riqnomasini](https://docs.docker.com/engine/install/ubuntu/) bajaring.
Docker data katalogi va mavjud volumelarni o‘chirmang.

Firewall: SSH porti 22 bo‘lmasa quyidagi 22 o‘rniga haqiqiy portni yozing:

```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

VPS provayder firewallida ham shu portlar ochiq bo‘lsin. DB porti internetga
chiqarilmaydi; API hostning loopback manziliga bog‘lanadi.

## 3. Server → GitHub: repositoryni SSH orqali ulash

Bu **clone/fetch** kaliti. U keyingi **Actions → server** kalitidan alohida.
[GitHub deploy key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys) bitta repositoryga ruxsat beradi.

Serverda (fayl avvaldan mavjud bo‘lsa uni qayta yaratmang):

```bash
install -d -m 700 /root/.ssh
ssh-keygen -t ed25519 -f /root/.ssh/neoavlod_git -C "neoavlod-vps-github-readonly" -N ''
cat /root/.ssh/neoavlod_git.pub
```

Chiqqan **public** kalitni repositoryda **Settings → Deploy keys → Add deploy key**
ga qo‘shing. Nomi: `VPS read-only`. **Allow write access** ni yoqmang.
Private kalit (`neoavlod_git`, `.pub` emas) serverda qoladi.

GitHub serverining tekshirilgan public host kalitini kiriting:

```bash
printf '%s\n' 'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl' >> /root/.ssh/known_hosts
chmod 600 /root/.ssh/known_hosts

ssh -i /root/.ssh/neoavlod_git -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -T git@github.com
```

`Hi ...! You've successfully authenticated, but GitHub does not provide shell access.`
— muvaffaqiyat; GitHub shell bermagani uchun bu tekshiruv exit code 1 berishi mumkin.
Host key o‘zgarsa, yangi kalitni [rasmiy fingerprint sahifasi](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints) orqali tekshiring;
`StrictHostKeyChecking=no` ishlatmang.

Endi **aynan `/root/` ichiga clone**:

```bash
cd /root
GIT_SSH_COMMAND='ssh -i /root/.ssh/neoavlod_git -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes' \
  git clone git@github.com:software-engineer006/NeoAvlodLMS.git
cd /root/NeoAvlodLMS

git config core.sshCommand 'ssh -i /root/.ssh/neoavlod_git -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes'
git fetch origin main
git log -1 --oneline origin/main
```

`/root/NeoAvlodLMS` avvaldan mavjud bo‘lsa, clone’ni qayta bajarmang; shu katalogda
`git config`, `git fetch` qadamlarini bajaring.

## 4. DNS: uchala domen ham VPSga qarasin

DNS boshqaruv panelida:

| Type | Host/name | Value |
|---|---|---|
| A | `admin` | `189.74.99.79` |
| A | `teacher` | `189.74.99.79` |
| A | `api` | `189.74.99.79` |

IPv6 ishlatilmasa AAAA kerak emas. AAAA mavjud bo‘lsa VPSning ishlaydigan IPv6
manziliga qarashi kerak. Cloudflare bo‘lsa dastlab **DNS only** rejimini tanlang.

Serverda:

```bash
dig @1.1.1.1 admin.eduneo.uz A +short
dig @1.1.1.1 teacher.eduneo.uz A +short
dig @1.1.1.1 api.eduneo.uz A +short
dig @8.8.8.8 api.eduneo.uz A +short
```

Har birida kerakli public IP ko‘rinsin. `NXDOMAIN` bo‘lsa yozuvni tuzating va DNS
javoblari yangilanishini kuting; Certbotni takrorlash hali yordam bermaydi.

## 5. Nginx orqali birinchi TLS sertifikatini olish

Nginx 80-portni ishlatib turganida **webroot** ishlatiladi. Nginxni to‘xtatish
kerak emas. HTTPS konfiguratsiyasini sertifikat olinmasidan oldin o‘rnatmang.

Ubuntu hostning `/etc/nginx/nginx.conf` faylida `http { ... }` ichiga
`server_names_hash_bucket_size 64;` yozing. Mavjud shu sozlama `32` bo‘lsa
uni `64` ga almashtiring; `# server_names_hash_bucket_size 64;` bo‘lsa
kommentariyni olib tashlang. Bir marta yozilsin; `server { ... }` ichiga yozmang.
Repo `nginx/nginx.conf` fayli Docker smoke uchun ishlatiladi; hostning asosiy
konfiguratsiyasi boshqa saytlarni saqlash uchun avtomatik almashtirilmaydi.

```bash
cp -a /etc/nginx/nginx.conf "/etc/nginx/nginx.conf.bak-$(date +%Y%m%d-%H%M%S)"
nano /etc/nginx/nginx.conf
```

Bu sozlama `could not build server_names_hash ... size: 32` xatosini
[Nginx rasmiy qo‘llanmasi](https://nginx.org/en/docs/http/server_names.html#optimization)ga mos tuzatadi.

```bash
cd /root/NeoAvlodLMS
install -d -m 755 /var/www/certbot/.well-known/acme-challenge
install -d -m 755 /var/www/neoavlod/releases
install -d -m 755 /opt/neoavlod/releases /opt/neoavlod/bin
install -d -m 700 /var/backups/neoavlod

install -m 644 nginx/acme-http.conf /etc/nginx/conf.d/neoavlod-acme.conf
nginx -t && systemctl reload nginx
printf 'neoavlod-acme-ok\n' > /var/www/certbot/.well-known/acme-challenge/check

curl -fsS http://admin.eduneo.uz/.well-known/acme-challenge/check
curl -fsS http://teacher.eduneo.uz/.well-known/acme-challenge/check
curl -fsS http://api.eduneo.uz/.well-known/acme-challenge/check
```

Uchalasida `neoavlod-acme-ok` chiqsin. Agar eski NeoAvlod 80-port konfiguratsiyasi
shu domenlar bilan o‘rnatilgan bo‘lsa, uning nusxasini saqlab olib, bootstrap
`neoavlod-acme.conf` bilan dublikat server bloklarini bartaraf eting.

`nginx -t` xato bersa keyingi bosqichga o‘tmang. Reload qabul qilinmaganida
oldingi konfiguratsiya ishlashda davom etadi va ACME URL 404 qaytarishi mumkin.
DNSdan alohida local Nginx tekshiruvi:

```bash
for host in admin.eduneo.uz teacher.eduneo.uz api.eduneo.uz; do
  curl -fsS -H "Host: $host" http://127.0.0.1/.well-known/acme-challenge/check
done
```

Local so‘rov ishlasa, yuqoridagi uchta public URLni ham tekshiring.
Terminalga `http://...` manzilni yozing; Markdown `[http://...](http://...)`
ko‘rinishini nusxalamang. Uchala public URL 200 bo‘lganidan keyin sertifikat oling.

Bitta nomlangan SAN sertifikat, uchala domen uchun:

```bash
certbot certonly --webroot -w /var/www/certbot \
  --cert-name eduneo.uz \
  -d admin.eduneo.uz -d teacher.eduneo.uz -d api.eduneo.uz \
  --email admin@eduneo.uz --agree-tos --no-eff-email

ls -l /etc/letsencrypt/live/eduneo.uz/fullchain.pem /etc/letsencrypt/live/eduneo.uz/privkey.pem
```

Barcha TLS server bloklari shu **bir xil** sertifikat yo‘lini ishlatadi.
Oldingi `--standalone` sertifikati `live/admin.eduneo.uz` ostida bo‘lsa, yuqoridagi
buyruq bilan `eduneo.uz` nomli sertifikatni yarating; eski fayllarni o‘chirish shart emas.

Renewal va Nginx reload hook:

```bash
install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/neoavlod-nginx.sh <<'EOF_HOOK'
#!/bin/sh
set -eu
nginx -t
systemctl reload nginx
EOF_HOOK
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/neoavlod-nginx.sh
systemctl enable --now certbot.timer
certbot renew --cert-name eduneo.uz --dry-run
```

Webroot va deploy hook [Certbot qo‘llanmasi](https://eff-certbot.readthedocs.io/en/stable/using.html#webroot)ga mos.
Mavjud boshqa standalone sertifikatlar renewal’i ham server to‘xtashini talab
qilishi mumkin; `eduneo.uz` sertifikati webroot bilan yangilanadi.

## 6. Production env va server operator skriptlari

```bash
cd /root/NeoAvlodLMS
bash scripts/deploy/init_production_env.sh
install -m 755 scripts/deploy/common.sh scripts/deploy/server_deploy.sh scripts/deploy/ci-entrypoint.sh /opt/neoavlod/bin/
stat -c '%a %n' /opt/neoavlod/.env.production
```

Skript DB paroli, security secret va Fernet kalitini yaratib, `chmod 600` bilan
saqlaydi; secretlar ekranga chiqarilmaydi. Mavjud faylni qayta yozmaydi.
Kalitlarni keyingi deploylarda almashtirmang: saqlangan bot tokeni ularning
barqaror bo‘lishiga bog‘liq. `API_PORT=8000` saqlansin — Nginx upstream shu portda.

Agar eski production DB/env mavjud bo‘lsa, o‘sha env va Docker project/volume’ni
saqlang; yangi init bilan ikkinchi bo‘sh bazani production deb qabul qilmang.
Ushbu tartibning project nomi doim `neoavlod-prod`.

## 7. Birinchi deployment va superadmin/Telegram bootstrap

Server tayyor, main’da lokal build ham commit qilingan bo‘lishi kerak:

```bash
cd /root/NeoAvlodLMS
RELEASE_SHA="$(git rev-parse origin/main)"
bash /opt/neoavlod/bin/server_deploy.sh "$RELEASE_SHA"

/opt/neoavlod/current/scripts/deploy/appctl.sh ps
curl -fsS https://api.eduneo.uz/api/v1/health
curl -fsS https://api.eduneo.uz/api/v1/ready
curl -fsS https://admin.eduneo.uz/release.txt
curl -fsS https://teacher.eduneo.uz/release.txt
```

Ikki `release.txt` main commit SHA’ni qaytaradi. Skript frontend checksumlarini
Dockerda tekshiradi, backendni SHA tag bilan build qiladi, backup oladi,
migratsiyani o‘tkazadi va bitta API/worker’ni almashtiradi. So‘ng Nginxni
tekshiradi va HTTPS orqali uchala domenni tekshiradi. Migratsiya paytida qisqa
uzilish mavjud; bu arxitektura zero-downtime deb hisoblanmaydi.

Frontend kataloglari avvaldan oddiy katalog bo‘lsa deploy to‘xtaydi. Ularni
zaxiralab boshqa nomga ko‘chiring; skript kerakli symlinklarni o‘zi yaratadi.
Server repo yangilansa deploy skripti Gitdagi exact SHA’dan ishlaydi.

Superadmin: haqiqiy telefoningizni kiriting; parol yashirin prompt orqali so‘raladi:

```bash
/opt/neoavlod/current/scripts/deploy/appctl.sh run --rm --no-deps api \
  python -m neoavlod.cli bootstrap \
  --username superadmin --phone '+998901234567' \
  --first-name Asosiy --last-name Admin
```

Parol 12–128 belgi, kamida 4 xil belgi bo‘lsin. Productionda local `1234` demo
hisoblari avtomatik yaratilmaydi. Natijadagi `onboarding_payload` ni saqlang.

Bot tokenini dastlab CLI orqali kiriting (yashirin prompt):

```bash
/opt/neoavlod/current/scripts/deploy/appctl.sh run --rm --no-deps api \
  python -m neoavlod.cli set-bot-token
/opt/neoavlod/current/scripts/deploy/appctl.sh logs --tail 50 worker
```

CLI `bot_username` qaytaradi. Bootstrap natijasidagi payload bilan quyidagi
havolani **o‘zingizning Telegram hisobingizda** oching va Start bosing:

```text
https://t.me/BOT_USERNAME?start=staff_BOOTSTRAP_AUTH_UUID
```

Masalan, CLI payload `staff_<uuid>` bo‘lsa, `start=` dan keyin aynan shu qiymat
yoziladi. Telegram bog‘langach `https://admin.eduneo.uz` da login qiling;
OTP haqiqiy Telegramga yuboriladi. Birinchi login oldidan UI orqali bot tokenini
kiritish mumkin emas, chunki loginning o‘zi botni talab qiladi.

## 8. Actions → server: cheklangan CI SSH kaliti

Bu kalit **kompyuteringizda** yaratiladi, private qismi GitHub Actions secretga,
public qismi serverga yoziladi. GitHub clone kalitini qayta ishlatmang:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/neoavlod_ci -C 'neoavlod-github-actions-deploy' -N ''
cat ~/.ssh/neoavlod_ci.pub
```

Public kalitning butun bir qatorini serverda quyidagi `PUBLIC_KEY` o‘rniga yozing:

```bash
install -d -m 700 /root/.ssh
touch /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
printf '%s\n' 'restrict,command="/opt/neoavlod/bin/ci-entrypoint.sh" PUBLIC_KEY' >> /root/.ssh/authorized_keys
```

`PUBLIC_KEY` o‘rnida `ssh-ed25519 AAAA... neoavlod-github-actions-deploy` bo‘ladi.
Mavjud administrator kalitlarini o‘chirmang. CI kalitida faqat `deploy <SHA>` va
`rollback` buyruqlari ruxsat etiladi; umumiy shell/port forwarding berilmaydi.
Root public-key login VPSda yoqilgan bo‘lishi kerak; SSH sozlamalarini o‘zgartirish
zarur bo‘lsa server konsolini va mavjud sessiyani ochiq saqlang.

Server host public kaliti va fingerprintini serverning ishonchli konsolida oling:

```bash
cat /etc/ssh/ssh_host_ed25519_key.pub
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

`SSH_KNOWN_HOSTS` qiymati port 22 uchun:

```text
189.74.99.79 ssh-ed25519 AAAA...SERVER_HOST_PUBLIC_KEY...
```

Port 2222 bo‘lsa: `[189.74.99.79]:2222 ssh-ed25519 AAAA...`.
Bu `/etc/ssh/ssh_host_ed25519_key.pub` dagi kalit; deploy public kaliti emas.
Tekshirilmagan `ssh-keyscan` natijasini avtomatik ishonchli deb qabul qilmang.

Repositoryda **Settings → Environments → New environment → production**
yarating. Deployment branches: faqat `main`. Environment secrets:

| Secret | Qiymati |
|---|---|
| `SSH_HOST` | `189.74.99.79` |
| `SSH_USER` | `root` |
| `SSH_PORT` | `22` yoki haqiqiy SSH port |
| `SSH_PRIVATE_KEY` | Kompyuterdagi `~/.ssh/neoavlod_ci` private faylining to‘liq tarkibi |
| `SSH_KNOWN_HOSTS` | Yuqoridagi tekshirilgan server host-key qatori |

Secretni GitHub UIga to‘g‘ridan-to‘g‘ri kiriting; repository, commit yoki logga
yozmang. Avtomatik deployment istasangiz environment uchun qo‘lda approval
qoidasi qo‘ymang. PR testlari production secretsga kira olmaydi.

VPSga SSH orqali kirish paroli `SSH_PRIVATE_KEY` emas. Bu secretga
`-----BEGIN OPENSSH PRIVATE KEY-----` dan `-----END OPENSSH PRIVATE KEY-----`
gacha bo‘lgan butun fayl tarkibi, qatorlari saqlangan holda kiritiladi.

## 9. Keyingi o‘zgarishlar: build → commit → push → avtomatik deploy

Kompyuteringizda har frontend o‘zgarishidan keyin:

```bash
cd /Users/dulmurod/NeoAvlodLMS
scripts/deploy/build_frontend.sh

git add -A
git diff --cached --stat
git commit -m "Describe the change"
git push origin main
```

Faqat backend o‘zgarsa va frontend manbalari o‘zgarmasa, oldingi frontend release
saqlanadi; backend yangi SHA image sifatida yangilanadi. Frontend manbasi yoki
lock/config/testlari o‘zgarsa buildni qayta tayyorlang — CI mosligini tekshiradi.
GitHub **Actions → NeoAvlod CI and Production Deploy** dagi test va deploy
joblarining yashil tugashini kuting. Deploy eski queued commitni main’dagi yangi
commit ustidan o‘rnatmaydi: joriy main SHAga mos bo‘lmasa to‘xtaydi.

Birinchi secrets sozlangach yoki deployni qayta boshlash uchun:
**Actions → NeoAvlod CI and Production Deploy → Run workflow → Branch main → action deploy**.
Serverda qo‘lda `git pull` yoki frontend build qilish kerak emas.

## 10. Rollback va nosozliklarni ko‘rish

Serverda oldingi muvaffaqiyatli **backend image va ikkala frontend**ga qaytish:

```bash
/opt/neoavlod/current/scripts/deploy/rollback.sh
```

Yoki Actions **Run workflow → main → action rollback**.
Aniq saqlangan muvaffaqiyatli releasega:

```bash
/opt/neoavlod/current/scripts/deploy/rollback.sh FULL_PREVIOUS_COMMIT_SHA
```

Deploy xatosi image, migration, API/worker, Nginx yoki HTTPS tekshiruv bosqichida
chiqsa skript avvalgi release mavjud bo‘lganda uni tiklashga urinadi. Birinchi
deploy xatosida oldingi release bo‘lmagani ochiq ko‘rsatiladi. Rollback health
xatosi muvaffaqiyat deb belgilanmaydi; Actions job ham xato bilan tugaydi.

DB schema avtomatik downgrade/restore qilinmaydi. Migratsiyalar oldingi backend
bilan mos bo‘lishi kerak (avval qo‘shish, keyingi release’da eski maydonni olib
tashlash). Mos bo‘lmagan migratsiya uchun alohida maintenance/restore rejasi kerak.

```bash
/opt/neoavlod/current/scripts/deploy/appctl.sh ps
/opt/neoavlod/current/scripts/deploy/appctl.sh logs --tail 100 api worker
nginx -t
journalctl -u nginx -n 50 --no-pager
```

`/opt/neoavlod/releases/<SHA>/.successful` faqat tekshirilgan release’da yaratiladi.
Failed release diagnostika uchun qoladi. Release/image/DB volumelar avtomatik
prune qilinmaydi. Diskni kuzating; current va `.previous_release` dagi release/image
juftliklarini saqlang, qolganlarini tekshirib qo‘lda tozalang. `docker system prune -a`
rollback imagelarini yo‘qotishi mumkin; `docker compose down -v` production DBni o‘chiradi.

## 11. Backup va tiklash

Qo‘lda:

```bash
/opt/neoavlod/current/scripts/deploy/backup.sh
```

Kunlik 03:00 **server timezone** bo‘yicha (`timedatectl` bilan tekshiring):

```bash
cat > /etc/cron.d/neoavlod-backup <<'EOF_CRON'
0 3 * * * root /opt/neoavlod/current/scripts/deploy/backup.sh >> /var/log/neoavlod-backup.log 2>&1
EOF_CRON
chmod 644 /etc/cron.d/neoavlod-backup
```

Backup tugamaguncha deploy boshlanmaydi; ikkisi bir xil lock ishlatadi.
Kundalik va migration-oldi dump’larni serverdan tashqariga ham nusxalang.
Avtomatik o‘chirish yo‘q; retentionni tekshirilgan backup rejangizga mos yuriting.

Foydalanuvchi profil rasmlari (`/app/media`) `neoavlod-prod_media-data` docker volume’ida saqlanadi.
Media fayllarini arxivlash:

```bash
docker run --rm -v neoavlod-prod_media-data:/media -v /var/backups/neoavlod:/backup alpine \
  tar czf "/backup/neoavlod_media_$(date +%Y%m%d_%H%M%S).tar.gz" -C /media .
```

Media arxivini qayta tiklash:

```bash
docker run --rm -v neoavlod-prod_media-data:/media -v /var/backups/neoavlod:/backup alpine \
  tar xzf /backup/YOUR_MEDIA_BACKUP.tar.gz -C /media
```

Dump formatini yozmasdan tekshirish:

```bash
BACKUP_FILE=/var/backups/neoavlod/YOUR_BACKUP.dump
/opt/neoavlod/current/scripts/deploy/appctl.sh exec -T database pg_restore --list < "$BACKUP_FILE"
```

**Tiklash mavjud DB ma’lumotlarini almashtiradi.** Ishlayotgan bazadan yangi backup
oling, tanlangan dump va unga mos backend release’ni tekshiring. Maintenance
sessiyasida, CI deploy yo‘q va boshqa operator yozmayotganida:

```bash
BACKUP_FILE=/var/backups/neoavlod/YOUR_BACKUP.dump
/opt/neoavlod/current/scripts/deploy/backup.sh
exec 9>/opt/neoavlod/.deploy.lock
flock -w 600 9
/opt/neoavlod/current/scripts/deploy/appctl.sh stop api worker
/opt/neoavlod/current/scripts/deploy/appctl.sh exec -T database sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --exit-on-error --single-transaction' < "$BACKUP_FILE"
# Shu dump schemaga mos joriy backend bo‘lsa:
/opt/neoavlod/current/scripts/deploy/appctl.sh up -d --no-deps --no-build --wait api worker
flock -u 9
curl -fsS https://api.eduneo.uz/api/v1/ready
```

Restore xato chiqsa appni to‘xtagan holda qoldirib xatoni tekshiring. Dumpga eski
backend kerak bo‘lsa lockni bo‘shatib tegishli saqlangan releasega rollback qiling;
migrations service’ni tasodifan qayta ishlatmang.

## 12. Serverga chiqarishdan keyingi qabul tekshiruvi

- Uch domenning A/AAAA, HTTP ACME va haqiqiy TLS sertifikati to‘g‘ri.
- API `/health` va `/ready` 200; ikkala portal `release.txt` kutilgan SHA.
- Superadmin Telegram link bilan bog‘langan; haqiqiy OTP login ishlaydi.
- Superadmin teacher/fan/guruh/talaba yaratadi; teacher faqat o‘z guruhlarini ko‘radi.
- Teacher davomat qoralamasini saqlaydi/yakunlaydi; ulangan ota-onaga haqiqiy Telegram xabari boradi.
- Admin davomat tarixini ko‘radi; portal/RBAC va CSRF cheklovlari ishlaydi.
- Main push bilan frontend va backend bir SHAga yangilanadi; Actions deploy yashil.
- Backup dump o‘qiladi; rollback oldingi image va ikkala frontendni tiklaydi.

Repositorydagi Docker smoke’lar bu oqimning infra qismini disposable muhitda
tekshiradi. Haqiqiy VPS SSH/DNS/TLS, GitHub secrets va Telegram yetkazilishini
serverda yuqoridagi qadamlar bilan alohida tasdiqlash kerak.

# Educenter import

To‘rtta Python CSV guruhi uchun optional private Docker import deploymentga
ulangan. Serverdagi paket, reviewed hash va backup/import tartibi:
[EDUCENTER_IMPORT.md](EDUCENTER_IMPORT.md). Xom CSV va credentiallar Gitga
qo‘shilmaydi; main push workflow test/deploy tartibi saqlanadi.
