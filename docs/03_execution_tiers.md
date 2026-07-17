# Discord VPS Agent — Execution Tiers

## Overview
Setiap command yang dieksekusi di VPS diklasifikasikan ke dalam 3 tier berdasarkan risikonya.
Klasifikasi dilakukan di `executor.py` sebelum command dijalankan.

---

## Tier ✅ — Auto Execute
Command langsung dijalankan tanpa notifikasi apapun.
Output langsung dikembalikan ke Discord.

**Kriteria:** Read-only, tidak mengubah state sistem, tidak bisa menyebabkan kerusakan.

```
# System info
ls, ls -la, pwd, whoami, id, uname -a, hostname
cat [file], head, tail, less, grep, find, locate
df -h, du -sh, free -h, top, htop, ps aux, uptime
env, printenv, echo

# Service status (read-only)
systemctl status [service]
pm2 status, pm2 list, pm2 logs [name] --lines [n]
nginx -t

# Network (read-only)
curl -s [url], wget --spider
ping -c 4 [host]
netstat -tulpn, ss -tulpn
nslookup, dig, whois

# Git (read-only)
git status, git log, git diff, git branch

# Log reading
journalctl -u [service] -n [lines]
tail -n [lines] /var/log/[file]
cat /proc/meminfo, cat /proc/cpuinfo
```

---

## Tier ⚠️ — Auto Execute + Notify
Command langsung dijalankan, tapi bot kirim notifikasi "FYI" ke Discord setelah eksekusi.

**Kriteria:** Mengubah state tapi reversible / tidak destruktif / operasi normal sehari-hari.

```
# Package management
apt update
apt install [package]
apt remove [package]
pip install [package]
npm install [package]

# Git operations
git pull
git fetch
git checkout [branch]

# File operations (non-destructive)
mkdir [dir]
cp [src] [dst]
mv [src] [dst]   ← hanya kalau bukan overwrite file penting
touch [file]
nano, vim [file]  ← edit file

# Service management
pm2 restart [name]
pm2 start [name]
pm2 stop [name]
systemctl restart [service]   ← via sudo whitelist
systemctl start [service]     ← via sudo whitelist
systemctl reload [service]    ← via sudo whitelist

# Cloudflared
sudo cloudflared tunnel [command]
```

Format notifikasi:
```
⚠️ Executed (auto):
$ pm2 restart markify-frontend
✅ Done — [output singkat]
```

---

## Tier 🔴 — Approval Required
Command TIDAK dijalankan sampai user klik [✅ Approve] di Discord.
Timeout 60 detik → auto-reject.

**Kriteria:** Destruktif, tidak bisa di-undo, atau berpotensi bricking server.

```
# Destructive file operations
rm -rf [path]
rm -f [file]
shred [file]
truncate [file]

# Permission changes berbahaya
chmod 777 [path]
chmod -R [path]
chown -R root [path]

# Service stop (bisa matiin production)
systemctl stop [service]
systemctl disable [service]
pm2 delete [name]

# System level
reboot, shutdown, poweroff
dd if= of=
mkfs.[type]
fdisk, parted

# Network / firewall changes
ufw reset
iptables -F
ufw delete [rule]

# Package removal yang kritikal
apt remove nginx
apt remove python3
apt purge [package]
apt autoremove

# Cron / scheduler
crontab -r   ← hapus semua cron

# Database
DROP TABLE, DROP DATABASE
DELETE FROM [table] (tanpa WHERE)

# Anything dengan sudo di luar whitelist
```

---

## Implementasi di `executor.py`

```python
TIER_AUTO = "auto"
TIER_NOTIFY = "notify"
TIER_APPROVAL = "approval"

def classify_command(command: str) -> str:
    """
    Klasifikasikan command ke tier yang sesuai.
    Default ke TIER_APPROVAL kalau tidak ada match (fail-safe).
    """
    cmd = command.strip().lower()

    # Tier 🔴 — cek dulu (prioritas tertinggi)
    DANGEROUS_PATTERNS = [
        "rm -rf", "rm -f", "shred", "truncate",
        "chmod 777", "chmod -r",
        "systemctl stop", "systemctl disable",
        "pm2 delete",
        "reboot", "shutdown", "poweroff",
        "dd if=", "mkfs", "fdisk", "parted",
        "ufw reset", "iptables -f",
        "drop table", "drop database",
        "delete from",
        "crontab -r",
        "apt remove nginx", "apt remove python3", "apt purge",
    ]
    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd:
            return TIER_APPROVAL

    # Tier ⚠️
    NOTIFY_PATTERNS = [
        "apt install", "apt update", "apt remove",
        "pip install", "npm install",
        "git pull", "git fetch", "git checkout",
        "mkdir", "cp ", "mv ", "touch ",
        "pm2 restart", "pm2 start", "pm2 stop",
        "systemctl restart", "systemctl start", "systemctl reload",
        "cloudflared",
    ]
    for pattern in NOTIFY_PATTERNS:
        if pattern in cmd:
            return TIER_NOTIFY

    # Default Tier ✅ untuk read-only commands
    SAFE_PATTERNS = [
        "ls", "cat", "head", "tail", "grep", "find",
        "df", "du", "free", "top", "ps", "uptime",
        "systemctl status", "pm2 status", "pm2 list", "pm2 logs",
        "git status", "git log", "git diff",
        "curl", "ping", "netstat", "ss", "nslookup",
        "journalctl", "uname", "whoami", "id",
    ]
    for pattern in SAFE_PATTERNS:
        if cmd.startswith(pattern) or f" {pattern}" in cmd:
            return TIER_AUTO

    # Fail-safe: kalau tidak dikenali → minta approval
    return TIER_APPROVAL
```

> **Fail-safe principle:** Command yang tidak dikenali → default ke TIER_APPROVAL, bukan auto-execute. Lebih baik terlalu hati-hati daripada eksekusi command berbahaya tanpa sadar.
