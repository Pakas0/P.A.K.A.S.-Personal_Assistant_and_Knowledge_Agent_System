# Discord VPS Agent — Sudo Whitelist Commands

## Overview
Bot berjalan sebagai user `bagasadmin` (non-root). Command yang memerlukan `sudo` hanya diizinkan untuk daftar di bawah ini via `/etc/sudoers.d/discord-agent-bot`.

Command sudo di luar whitelist ini akan **auto-reject** tanpa approval — bukan masuk tier 🔴.

---

## Sudoers File
Lokasi: `/etc/sudoers.d/discord-agent-bot`

```sudoers
# Discord Agent Bot — Sudo Whitelist
# Jangan edit manual, refer ke discord-agent-prd/04_whitelist_commands.md

Defaults:bagasadmin !requiretty

# Systemd Service Management
bagasadmin ALL=(ALL) NOPASSWD: /bin/systemctl start *
bagasadmin ALL=(ALL) NOPASSWD: /bin/systemctl stop *
bagasadmin ALL=(ALL) NOPASSWD: /bin/systemctl restart *
bagasadmin ALL=(ALL) NOPASSWD: /bin/systemctl reload *
bagasadmin ALL=(ALL) NOPASSWD: /bin/systemctl status *
bagasadmin ALL=(ALL) NOPASSWD: /bin/systemctl enable *
bagasadmin ALL=(ALL) NOPASSWD: /bin/systemctl disable *

# Nginx
bagasadmin ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t
bagasadmin ALL=(ALL) NOPASSWD: /usr/sbin/nginx -s reload

# Network & Firewall
bagasadmin ALL=(ALL) NOPASSWD: /usr/sbin/ufw status
bagasadmin ALL=(ALL) NOPASSWD: /usr/sbin/ufw status verbose
bagasadmin ALL=(ALL) NOPASSWD: /usr/sbin/ufw allow *
bagasadmin ALL=(ALL) NOPASSWD: /usr/sbin/ufw deny *
bagasadmin ALL=(ALL) NOPASSWD: /usr/sbin/ufw delete *
bagasadmin ALL=(ALL) NOPASSWD: /bin/netstat -tulpn
bagasadmin ALL=(ALL) NOPASSWD: /usr/bin/ss -tulpn

# System Logs & Info
bagasadmin ALL=(ALL) NOPASSWD: /bin/journalctl *
bagasadmin ALL=(ALL) NOPASSWD: /bin/dmesg
bagasadmin ALL=(ALL) NOPASSWD: /bin/cat /var/log/*
bagasadmin ALL=(ALL) NOPASSWD: /usr/bin/tail /var/log/*

# Package Management
bagasadmin ALL=(ALL) NOPASSWD: /usr/bin/apt update
bagasadmin ALL=(ALL) NOPASSWD: /usr/bin/apt install *
bagasadmin ALL=(ALL) NOPASSWD: /usr/bin/apt remove *
bagasadmin ALL=(ALL) NOPASSWD: /usr/bin/apt upgrade *
bagasadmin ALL=(ALL) NOPASSWD: /usr/bin/apt autoremove

# File Ownership (hanya ke bagasadmin)
bagasadmin ALL=(ALL) NOPASSWD: /bin/chown bagasadmin\:bagasadmin *

# Safe chmod only
bagasadmin ALL=(ALL) NOPASSWD: /bin/chmod 755 *
bagasadmin ALL=(ALL) NOPASSWD: /bin/chmod 644 *
bagasadmin ALL=(ALL) NOPASSWD: /bin/chmod 600 *
bagasadmin ALL=(ALL) NOPASSWD: /bin/chmod 700 *

# Cloudflared
bagasadmin ALL=(ALL) NOPASSWD: /usr/bin/cloudflared *

# Swap management (read-only)
bagasadmin ALL=(ALL) NOPASSWD: /sbin/swapon --show
```

---

## Setup Command
Jalankan sekali saat setup awal di VPS:

```bash
sudo visudo -f /etc/sudoers.d/discord-agent-bot
# paste isi sudoers file di atas

# Verifikasi syntax (jangan sampai salah, bisa lock out)
sudo visudo -c -f /etc/sudoers.d/discord-agent-bot

# Test
sudo -u bagasadmin sudo systemctl status nginx
```

---

## Yang TIDAK Ada di Whitelist (Intentional)

| Command | Alasan |
|---|---|
| `chmod 777` | Terlalu permissive, security risk |
| `chown root` | Bisa lock out user |
| `ufw reset` | Bisa cut off semua koneksi |
| `iptables -F` | Flush semua firewall rules |
| `apt purge` | Lebih destruktif dari `apt remove` |
| `systemctl mask` | Permanent disable service |
| `dd`, `mkfs`, `fdisk` | Bisa wipe disk |
| `reboot`, `shutdown` | Matiin VPS = Markify down |

> Command-command ini masuk tier 🔴 dan butuh approval, tapi tetap **tidak bisa dijalankan via sudo** karena tidak ada di whitelist. Bot akan reject dengan pesan: "Command ini tidak ada di sudo whitelist, tidak dapat dieksekusi."
