# Discord VPS Agent — Overview

## Deskripsi
Bot Discord pribadi yang berfungsi sebagai AI assistant + VPS manager. Bot ini memungkinkan pemilik untuk ngobrol dengan berbagai LLM model, sekaligus mengeksekusi perintah langsung ke VPS melalui interface Discord — lengkap dengan sistem approval, persistent memory per thread, dan monitoring dasar.

## Target User
- Single user (owner only) — `ALLOWED_USER_ID` di `.env`
- Private Discord server

## Tech Stack
| Komponen | Teknologi |
|---|---|
| Language | Python 3.11+ |
| Discord Library | `discord.py` |
| Database | SQLite (via `aiosqlite`) |
| LLM Providers | Google Gemini, Groq, Anthropic Claude |
| Process Manager | PM2 |
| Deployment | VPS (Ubuntu 24), GitHub untuk source |
| Sudo Management | `/etc/sudoers.d/` NOPASSWD whitelist |

## Struktur Folder
```
discord-agent/
├── .env
├── .gitignore
├── requirements.txt
├── main.py                  # Entry point, load semua cogs
├── config.py                # Load env, constants, model list
├── database.py              # SQLite init, helper functions
├── executor.py              # Shell command executor + tier classification
├── monitor.py               # Background task: RAM/disk/service alerting
│
├── cogs/
│   ├── chat.py              # AI chat handler (default + @override)
│   ├── vps.py               # VPS command slash commands
│   ├── pentest.py           # Pentest workflow commands
│   └── settings.py          # /setmodel, /setdefault, dll
│
├── utils/
│   ├── llm.py               # Unified LLM caller (Gemini/Groq/Claude)
│   ├── approval.py          # Discord button approval system
│   └── logger.py            # Logging setup
│
└── data/
    └── memory.db            # SQLite database (gitignored)
```

## Environment Variables (`.env`)
```env
DISCORD_TOKEN=                  # Token bot Discord
DISCORD_GUILD_ID=               # ID server Discord kamu
ALLOWED_USER_ID=                # Discord User ID kamu (owner only)
ALERT_CHANNEL_ID=               # Channel ID untuk kirim alert monitoring

GEMINI_API_KEY=                 # Google AI Studio
GROQ_API_KEY=                   # Groq Console
ANTHROPIC_API_KEY=              # Anthropic (opsional, berbayar)

DEFAULT_MODEL=gemini             # Model default saat bot start
```

## Model yang Didukung
| Alias | Provider | Model ID | Gratis? |
|---|---|---|---|
| `gemini` | Google | `gemini-2.0-flash` | ✅ Free tier |
| `groq` | Groq | `llama-3.3-70b-versatile` | ✅ Free tier |
| `claude` | Anthropic | `claude-haiku-4-5` | ❌ Berbayar |

## Referensi File Lain
- `02_features.md` — Detail fitur dan flow
- `03_execution_tiers.md` — Tier eksekusi command
- `04_whitelist_commands.md` — Daftar command sudo whitelist
- `05_database_schema.md` — Schema SQLite
- `06_setup_guide.md` — Langkah setup dari nol
