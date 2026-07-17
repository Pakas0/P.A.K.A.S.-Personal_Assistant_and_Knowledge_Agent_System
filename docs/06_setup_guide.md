# Discord VPS Agent — Setup Guide

## Prerequisites
- VPS Ubuntu 24 dengan user `bagasadmin`
- Python 3.11+ terinstall
- PM2 terinstall (sudah ada dari setup Markify)
- Bot Discord sudah dibuat, token sudah didapat
- API key minimal 1 provider (Gemini / Groq)

---

## Step 1: Clone & Setup di Laptop (Development)

```bash
# Clone repo (buat dulu di GitHub)
git clone https://github.com/Pakas0/discord-agent.git
cd discord-agent

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install discord.py google-generativeai groq anthropic aiosqlite python-dotenv

# Generate requirements.txt
pip freeze > requirements.txt

# Buat .env dari template
cp .env.example .env
# Edit .env dengan nilai yang sebenarnya
```

---

## Step 2: Setup Sudoers di VPS

```bash
# SSH ke VPS
ssh bagasadmin@<IP_VPS>

# Buat sudoers file
sudo visudo -f /etc/sudoers.d/discord-agent-bot
# Paste isi dari 04_whitelist_commands.md

# Verifikasi syntax (WAJIB sebelum save)
sudo visudo -c -f /etc/sudoers.d/discord-agent-bot

# Set permission yang benar
sudo chmod 440 /etc/sudoers.d/discord-agent-bot
```

---

## Step 3: Setup di VPS

```bash
# Di VPS
mkdir ~/discord-agent && cd ~/discord-agent

# Clone dari GitHub
git clone https://github.com/Pakas0/discord-agent.git .

# Setup venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Buat .env (ISI MANUAL, jangan di-push ke GitHub)
nano .env

# Buat folder data
mkdir data
```

---

## Step 4: Jalankan via PM2

```bash
# Pastikan venv aktif
source ~/discord-agent/venv/bin/activate

# Start via PM2
pm2 start main.py \
  --name discord-agent \
  --interpreter ~/discord-agent/venv/bin/python3 \
  --cwd ~/discord-agent

# Save PM2 config supaya auto-start
pm2 save

# Cek status
pm2 status
pm2 logs discord-agent --lines 50
```

---

## Step 5: Verifikasi Bot Berjalan

Di Discord:
1. Buka private server kamu
2. Ketik `/ping` → bot harus reply dengan latency
3. Ketik `/modelinfo` → harus tampil model default
4. Ketik `/status` → harus tampil info RAM/disk VPS
5. Coba chat biasa → bot harus reply dengan AI

---

## Workflow Update (Laptop → VPS)

```bash
# Di laptop setelah ada perubahan kode:
git add .
git commit -m "feat: tambah fitur X"
git push origin main

# Di VPS:
cd ~/discord-agent
git pull origin main
pm2 restart discord-agent
```

Atau bisa minta bot sendiri untuk update dirinya:
```
"update bot dari github dan restart"
    ↓ bot jalankan:
$ cd ~/discord-agent && git pull && pm2 restart discord-agent
    ↓ tier ⚠️ auto+notify
```

---

## Pentest Tools Setup (Opsional)
Install tools yang dibutuhkan untuk fitur pentest:

```bash
sudo apt update
sudo apt install -y nmap nikto gobuster hydra sqlmap
```

---

## Troubleshooting

### Bot tidak online di Discord
```bash
pm2 logs discord-agent --lines 100
# Cek apakah DISCORD_TOKEN valid
# Cek apakah ALLOWED_USER_ID benar
```

### Command tidak bisa dieksekusi
```bash
# Test sudo whitelist manual
sudo systemctl status nginx
# Kalau minta password, berarti sudoers belum setup dengan benar
```

### Memory DB error
```bash
ls -la ~/discord-agent/data/
# Kalau folder tidak ada:
mkdir ~/discord-agent/data
pm2 restart discord-agent
```

### Bot tidak respond pesan
- Pastikan **Message Content Intent** aktif di Discord Developer Portal
- Pastikan bot ada di server dan punya akses ke channel
- Cek `ALLOWED_USER_ID` sudah benar (hanya owner yang bisa interact)
