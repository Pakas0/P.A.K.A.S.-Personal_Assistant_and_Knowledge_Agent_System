# Discord VPS Agent — Features & Flow

## 1. AI Chat

### Flow Normal (Default Model)
```
User kirim pesan biasa di channel/thread
    ↓
Bot detect bukan slash command
    ↓
Ambil conversation history dari SQLite (thread_id)
    ↓
Kirim ke LLM default (dari /setmodel atau DEFAULT_MODEL di .env)
    ↓
Simpan pesan user + respons ke SQLite
    ↓
Bot reply di thread yang sama
```

### Override Model Per-Message
User bisa prefix pesan dengan `@gemini`, `@groq`, atau `@claude`:
```
@claude jelasin perbedaan TCP sama UDP
@groq buatin bash script untuk backup folder
@gemini review kode ini: [paste kode]
```
Bot detect prefix → gunakan model yang disebutkan untuk pesan itu saja → model default tidak berubah.

### Slash Commands Chat
| Command | Fungsi |
|---|---|
| `/setmodel [gemini\|groq\|claude]` | Ganti default model |
| `/newchat` | Buat Discord thread baru = conversation baru |
| `/clearchat` | Hapus history conversation di thread ini |
| `/modelinfo` | Tampilkan model aktif saat ini |

### Thread sebagai Conversation
- Setiap Discord thread = 1 conversation context
- History disimpan di SQLite per `thread_id`
- `/newchat` → bot buat thread baru otomatis dengan nama timestamp
- Pindah thread = pindah context, kayak "New Chat" di Claude/GPT

---

## 2. VPS Management

### Slash Commands VPS
| Command | Fungsi | Tier |
|---|---|---|
| `/status` | Tampilkan RAM, disk, CPU, uptime | ✅ Auto |
| `/services` | List semua service systemd + PM2 | ✅ Auto |
| `/logs [service] [lines]` | Tail log service | ✅ Auto |
| `/exec [command]` | Eksekusi shell command | Tergantung tier |
| `/restart [service]` | Restart systemd/PM2 service | ⚠️ Auto+notify |
| `/install [package]` | apt install package | ⚠️ Auto+notify |

### Natural Language VPS Command
User bisa minta ke AI dalam bahasa natural, AI yang translate ke command:
```
"cek kenapa markify-backend makan RAM banyak"
    ↓ AI translate jadi:
$ ps aux | grep gunicorn
$ cat /proc/[pid]/status
    ↓ eksekusi sesuai tier
    ↓ hasilnya dikirim balik + AI analisis
```

### Approval System (Tier 🔴)
Tampilan di Discord:
```
🔴 Command berikut memerlukan approval:
$ rm -rf ~/markify/old-backup

⚠️ Tindakan ini TIDAK DAPAT dibatalkan!
Timeout: 60 detik

[✅ Approve]  [❌ Reject]
```
- Hanya `ALLOWED_USER_ID` yang bisa klik button
- Timeout 60 detik → auto-reject kalau tidak ada respons
- Setelah approve/reject → button disabled

---

## 3. Pentest Workflow

### Aktivasi
Hanya berjalan kalau user eksplisit minta:
```
"pentest VPS ku sekarang"
"jalanin full security audit"
"/pentest run"
```

### Flow Pentest
```
User request pentest
    ↓
Bot konfirmasi: "Memulai pentest terhadap [IP VPS]. Lanjutkan?" [Yes] [No]
    ↓ Approve
Bot jalankan tahapan secara berurutan:
    1. Recon       → nmap, whois, dns enum
    2. Enumeration → service version, OS detection
    3. Vuln Scan   → nikto, nmap scripts
    4. Exploit     → sesuai temuan (dengan approval per-step)
    5. Privesc     → cek SUID, sudo misconfig, cron jobs
    ↓
Generate laporan markdown → kirim sebagai file di Discord
```

### Slash Commands Pentest
| Command | Fungsi |
|---|---|
| `/pentest run` | Full pentest workflow |
| `/pentest recon` | Hanya tahap recon |
| `/pentest report` | Generate ulang laporan terakhir |

### Tools yang Digunakan
- `nmap` — port scan + service detection
- `nikto` — web vulnerability scanner
- `gobuster` — directory bruteforce
- `hydra` — credential testing (target sendiri)
- `sqlmap` — SQL injection scan
- Manual privilege escalation checks via bash

> ⚠️ **Disclaimer**: Fitur pentest hanya untuk digunakan pada VPS milik sendiri. Penggunaan terhadap sistem pihak lain adalah ilegal.

---

## 4. Basic Monitoring & Alerting

### Background Task (Berjalan tiap 5 menit)
Bot cek kondisi VPS secara berkala tanpa LLM:
```python
checks = [
    RAM usage > 90%,
    Disk usage > 85%,
    markify-backend down,
    markify-frontend (PM2) down,
    cloudflared down,
    nginx down,
]
```

### Format Alert di Discord
```
⚠️ ALERT — RAM Critical
RAM usage: 94% (816MB / 867MB)
Swap usage: 78% (1.6GB / 2GB)
Time: 2026-07-01 03:15:00 UTC

Top processes by RAM:
1. gunicorn [939] — 337MB
2. node [markify] — 24MB
```

Alert dikirim ke `ALERT_CHANNEL_ID` yang di-set di `.env`.
Alert tidak repeat dalam 30 menit untuk kondisi yang sama (cooldown).

---

## 5. Settings

| Command | Fungsi |
|---|---|
| `/setmodel [model]` | Ganti default model |
| `/settings` | Tampilkan semua settings aktif |
| `/ping` | Cek bot online + latency |
| `/help` | Daftar semua command |

---

## 6. Fitur Cerdas (RAM-Optimized)
*(Baru ditambahkan)*
1. **Auto Web Search**: Bot akan secara otomatis melakukan pencarian web melalui Tavily API jika Anda menanyakan hal yang membutuhkan koneksi internet atau info waktu-nyata.
2. **Session Context Summarization**: Thread yang memiliki riwayat > 30 pesan akan otomatis diringkas untuk menghemat token memori konteks pada bot LLM.
3. **Log Auto-Summarizer**: Hasil eksekusi log yang sangat panjang otomatis dirangkum berdasarkan anomali atau pesan *error* penting.
4. **Command Semantic Search (`/history`)**: Anda bisa mencari riwayat command secara natural ("Command apa yang mengubah chmod?").
5. **Daily Health Digest**: Secara otomatis bot mengirimkan summary kondisi VPS harian (pada UTC 0) berdasarkan eksekusi perintah harian dan alert sebelumnya.
6. **Smart Explain Error**: Jika hasil command `/exec` (ataupun *natural language command*) Anda gagal / `exit_code != 0`, AI akan mengirim pesan penjelasan dan solusi otomatis.
7. **Long Message Auto-Split**: Menghindari batasan limit *Discord* untuk pesan-pesan instruksi yang panjang (diberikan TL;DR secara singkat).
8. **Auto Document Generation**: Mampu menggenerate dokumen laporan (format `.docx`, `.xlsx`, `.pptx`, `.pdf`) menggunakan ekstensi AI dan mengirimkannya langsung ke Discord Anda via `discord.File` dengan basis Python-native murni tanpa *browser-renderer*.
9. **Auto Command Execution**: Bot dapat mengeksekusi perintah shell / bash secara otonom lewat bahasa manusia di chat. Sistem secara otomatis menolak setiap panggilan destruktif (Tier Approval) dan hanya mengizinkan perintah aman.
