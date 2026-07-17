# Discord VPS Agent — Agent Prompt

> Ini adalah instruksi untuk AI code agent yang akan mengimplementasikan project ini.
> Baca semua file PRD sebelum mulai coding.

---

## Konteks Project
Kamu diminta membangun Discord bot berbasis Python yang berfungsi sebagai AI assistant + VPS manager pribadi untuk seorang developer. Bot ini akan di-deploy di Ubuntu VPS dengan RAM terbatas (1GB).

## File PRD yang Harus Dibaca Dulu
1. `01_overview.md` — Struktur folder, tech stack, environment variables
2. `02_features.md` — Detail semua fitur dan flow
3. `03_execution_tiers.md` — Sistem tier eksekusi command + implementasi `executor.py`
4. `04_whitelist_commands.md` — Sudoers whitelist untuk sudo commands
5. `05_database_schema.md` — Schema SQLite + helper functions
6. `06_setup_guide.md` — Cara setup di VPS

---

## Urutan Implementasi yang Disarankan

### Phase 1 — Foundation
1. Buat struktur folder sesuai `01_overview.md`
2. Buat `config.py` — load `.env`, constants, model list
3. Buat `database.py` — init SQLite, semua helper functions dari `05_database_schema.md`
4. Buat `.env.example` — template tanpa nilai asli
5. Buat `.gitignore` — exclude `.env`, `venv/`, `data/`, `__pycache__/`
6. Buat `requirements.txt`

### Phase 2 — Core Bot
7. Buat `main.py` — entry point, setup Discord intents, load cogs
8. Buat `utils/logger.py` — logging setup
9. Buat `utils/llm.py` — unified LLM caller untuk Gemini, Groq, Claude
10. Buat `cogs/settings.py` — `/setmodel`, `/modelinfo`, `/ping`, `/help`

### Phase 3 — AI Chat
11. Buat `cogs/chat.py`:
    - Handle pesan biasa (bukan slash command) → kirim ke LLM default
    - Detect prefix `@gemini`, `@groq`, `@claude` → override model
    - Ambil + simpan history dari SQLite per `thread_id`
    - `/newchat` → buat Discord thread baru
    - `/clearchat` → hapus history thread ini

### Phase 4 — VPS Execution
12. Buat `executor.py`:
    - `classify_command()` sesuai `03_execution_tiers.md`
    - `execute_command()` — jalankan via `subprocess`, return output + exit code
    - Handle sudo commands (cek whitelist dulu)
13. Buat `utils/approval.py`:
    - Discord View dengan button [✅ Approve] [❌ Reject]
    - Timeout 60 detik → auto-reject
    - Hanya `ALLOWED_USER_ID` yang bisa interact
14. Buat `cogs/vps.py`:
    - `/status` — tampilkan RAM, disk, CPU, uptime
    - `/services` — list service systemd + PM2
    - `/logs [service] [lines]` — tail logs
    - `/exec [command]` — eksekusi dengan tier classification
    - `/restart [service]` — restart service
    - Natural language → AI translate → execute

### Phase 5 — Monitoring
15. Buat `monitor.py`:
    - Background task tiap 5 menit (tanpa LLM)
    - Cek RAM > 90%, disk > 85%, service down
    - Kirim alert ke `ALERT_CHANNEL_ID` dengan cooldown 30 menit
    - Format alert sesuai `02_features.md`

### Phase 6 — Pentest
16. Buat `cogs/pentest.py`:
    - `/pentest run`, `/pentest recon`, `/pentest report`
    - Flow: konfirmasi → recon → enum → vuln scan → exploit (approval per step) → laporan
    - Generate laporan markdown → kirim sebagai file attachment Discord

---

## Hal-hal Penting

### Security
- Selalu validasi `ALLOWED_USER_ID` sebelum proses command apapun
- Fail-safe: command tidak dikenali → TIER_APPROVAL, bukan auto-execute
- Sudo command di luar whitelist → reject, jangan masuk approval flow
- Jangan pernah log API keys atau Discord token

### Memory Management (VPS RAM mepet)
- Batasi history yang dikirim ke LLM maksimal 20 pesan terakhir
- Jangan load semua history ke memory — query per request
- Gunakan `aiosqlite` (async) agar tidak blocking Discord event loop

### Error Handling
- Semua command execution harus punya try/catch
- Kalau LLM API error → fallback ke pesan error yang informatif, jangan crash
- Kalau SQLite error → log dan notify user, jangan crash bot

### Discord Specifics
- Gunakan `discord.py` dengan slash commands (`app_commands`)
- Sync slash commands saat bot ready: `await tree.sync(guild=GUILD)`
- Untuk reply panjang (>2000 karakter) → split atau kirim sebagai file

### Testing Lokal
- Bot bisa ditest di laptop sebelum deploy ke VPS
- Command execution di lokal akan jalankan di sistem laptop — pastikan aman
- Gunakan environment variable `ENV=development` untuk disable command execution berbahaya saat dev

---

## Output yang Diharapkan
Setelah implementasi selesai:
1. Semua file sesuai struktur di `01_overview.md`
2. `requirements.txt` lengkap
3. `.env.example` dengan semua key (tanpa nilai)
4. README.md singkat berisi cara setup dan daftar command
5. Kode siap di-push ke GitHub dan di-pull ke VPS
