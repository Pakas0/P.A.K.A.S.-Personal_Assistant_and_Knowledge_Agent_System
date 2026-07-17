# P.A.K.A.S. - Discord VPS Agent

P.A.K.A.S. is a personal AI assistant and VPS manager built as a Discord Bot. It integrates directly with your Ubuntu VPS allowing you to run monitoring, manage services, execute shell commands (with a safe tier-based approval system), and even chat with multiple LLMs via a unified interface.

## Prerequisites
- Python 3.11+
- Discord Bot Token with Message Content Intent enabled
- `ALLOWED_USER_ID` (Your Discord User ID)
- API Keys for the LLMs you want to use (Gemini, Groq, Anthropic, or OpenAI-compatible proxy via `NINER_ROUTER_URL`)

## Setup Instructions

1. **Clone and Install Dependencies:**
   ```bash
   git clone https://github.com/Pakas0/discord-agent.git
   cd discord-agent
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Environment Variables:**
   - Copy `.env.example` to `.env`
   - Fill in your Discord Token, User ID, Guild ID, Alert Channel ID, and API Keys.

3. **Sudoers Setup (For VPS management):**
   - Ensure the bot runs under a user like `bagasadmin`.
   - Setup the sudoers whitelist as per `docs/04_whitelist_commands.md` using `visudo`.

4. **Run the Bot:**
   ```bash
   python main.py
   ```
   *To run persistently on a VPS, use PM2 as detailed in `docs/06_setup_guide.md`.*

## Commands List

### Chat & Settings
- `@gemini`, `@groq`, `@claude` (prefix in chat) — Override model for the message.
- `/newchat` — Create a new thread for a fresh context.
- `/clearchat` — Clear the context of the current thread.
- `/setmodel` — Set the default LLM.
- `/modelinfo` — View current model configuration.
- `/ping` — Check latency.
- `/help` — View help.

### VPS Management
- `/status` — View VPS RAM, Disk, CPU, and Uptime.
- `/services` — List running systemd and PM2 services.
- `/logs [service] [lines]` — Tail logs for a service.
- `/restart [service]` — Restart a systemd/PM2 service.
- `/install [package]` — Install an apt package.
- `/exec [command]` — Run a shell command directly.
- `/do [intent]` — AI translates natural language into a shell command and executes it.

### Pentest (Use With Caution)
- `/pentest run` — Run full pentest workflow.
- `/pentest recon` — Run only the recon phase.
- `/pentest report` — Generate the last pentest report.

## Security
- Only `ALLOWED_USER_ID` can use the bot.
- All destructive shell commands require explicit button approval in Discord.
- Sudo commands not on the whitelist will fail.
