# Discord VPS Agent — Database Schema

## Overview
Database: SQLite via `aiosqlite`
Lokasi: `data/memory.db` (gitignored)
Init: otomatis saat bot pertama kali jalan via `database.py`

---

## Tables

### 1. `conversations`
Menyimpan semua pesan per thread (persistent memory).

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   TEXT NOT NULL,          -- Discord thread ID
    role        TEXT NOT NULL,          -- 'user' atau 'assistant'
    content     TEXT NOT NULL,          -- Isi pesan
    model       TEXT,                   -- Model yang digunakan (gemini/groq/claude)
    created_at  DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX idx_conversations_thread ON conversations(thread_id);
```

### 2. `settings`
Menyimpan konfigurasi per user/global.

```sql
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  DATETIME DEFAULT (datetime('now'))
);

-- Default values (di-insert saat init):
-- ('default_model', 'gemini')
-- ('alert_cooldown_minutes', '30')
-- ('monitoring_interval_minutes', '5')
```

### 3. `command_history`
Audit log semua command yang pernah dieksekusi.

```sql
CREATE TABLE IF NOT EXISTS command_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command     TEXT NOT NULL,
    tier        TEXT NOT NULL,          -- 'auto', 'notify', 'approval'
    approved    BOOLEAN,                -- NULL kalau auto, True/False kalau approval
    output      TEXT,                   -- Output command (truncated 2000 chars)
    exit_code   INTEGER,
    executed_at DATETIME DEFAULT (datetime('now'))
);
```

### 4. `alert_log`
Tracking alert yang sudah dikirim untuk cooldown.

```sql
CREATE TABLE IF NOT EXISTS alert_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type  TEXT NOT NULL,          -- 'ram', 'disk', 'service_down'
    detail      TEXT,                   -- Nama service / % usage
    sent_at     DATETIME DEFAULT (datetime('now'))
);
```

---

## Helper Functions (`database.py`)

```python
# Ambil conversation history untuk 1 thread
async def get_history(thread_id: str, limit: int = 20) -> list[dict]

# Simpan pesan ke history
async def save_message(thread_id: str, role: str, content: str, model: str = None)

# Hapus semua history di thread
async def clear_history(thread_id: str)

# Get/set settings
async def get_setting(key: str) -> str
async def set_setting(key: str, value: str)

# Log command execution
async def log_command(command: str, tier: str, approved: bool, output: str, exit_code: int)

# Cek apakah alert sudah dikirim dalam X menit terakhir
async def is_alert_on_cooldown(alert_type: str, detail: str, minutes: int = 30) -> bool

# Simpan alert yang baru dikirim
async def log_alert(alert_type: str, detail: str)
```

---

## Catatan
- History per thread dibatasi 20 pesan terakhir saat dikirim ke LLM (hemat token)
- `command_history` output di-truncate 2000 karakter
- Database di-backup manual via `/exec sqlite3 data/memory.db .dump > backup.sql`
