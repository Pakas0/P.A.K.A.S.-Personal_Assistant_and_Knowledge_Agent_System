import os
import aiosqlite
import logging
from config import DB_PATH, DATA_DIR

logger = logging.getLogger("discord_agent")

async def init_db():
    """Initialize the SQLite database with required tables and default settings."""
    # Ensure data directory exists
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    async with aiosqlite.connect(DB_PATH) as db:
        # Conversations Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id   TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                model       TEXT,
                created_at  DATETIME DEFAULT (datetime('now'))
            )
        ''')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_conversations_thread ON conversations(thread_id)')

        # Settings Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  DATETIME DEFAULT (datetime('now'))
            )
        ''')

        # Insert default settings if they don't exist
        default_settings = [
            ('default_model', 'gemini'),
            ('alert_cooldown_minutes', '30'),
            ('monitoring_interval_minutes', '5')
        ]
        await db.executemany('''
            INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)
        ''', default_settings)

        # Command History Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS command_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                command     TEXT NOT NULL,
                tier        TEXT NOT NULL,
                approved    BOOLEAN,
                output      TEXT,
                exit_code   INTEGER,
                executed_at DATETIME DEFAULT (datetime('now'))
            )
        ''')

        # Alert Log Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS alert_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type  TEXT NOT NULL,
                detail      TEXT,
                sent_at     DATETIME DEFAULT (datetime('now'))
            )
        ''')

        await db.commit()
        logger.info("Database initialized successfully.")

# --- Helper Functions ---

async def get_history(thread_id: str, limit: int = 20) -> list[dict]:
    """Get conversation history for a specific thread."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT role, content FROM conversations 
            WHERE thread_id = ? 
            ORDER BY id DESC LIMIT ?
        ''', (thread_id, limit)) as cursor:
            rows = await cursor.fetchall()
            # Reverse to maintain chronological order
            return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

async def save_message(thread_id: str, role: str, content: str, model: str = None):
    """Save a message to the conversation history."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO conversations (thread_id, role, content, model) 
            VALUES (?, ?, ?, ?)
        ''', (thread_id, role, content, model))
        await db.commit()

async def clear_history(thread_id: str):
    """Delete all history for a specific thread."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM conversations WHERE thread_id = ?', (thread_id,))
        await db.commit()

async def get_setting(key: str) -> str:
    """Retrieve a setting by key."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT value FROM settings WHERE key = ?', (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def set_setting(key: str, value: str):
    """Update or insert a setting."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO settings (key, value, updated_at) 
            VALUES (?, ?, datetime('now')) 
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')
        ''', (key, str(value)))
        await db.commit()

async def log_command(command: str, tier: str, approved: bool, output: str, exit_code: int):
    """Log a command execution to history."""
    # Truncate output to 2000 characters
    if output and len(output) > 2000:
        output = output[:1997] + "..."
        
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO command_history (command, tier, approved, output, exit_code) 
            VALUES (?, ?, ?, ?, ?)
        ''', (command, tier, approved, output, exit_code))
        await db.commit()

async def is_alert_on_cooldown(alert_type: str, detail: str, minutes: int = 30) -> bool:
    """Check if an alert of the given type and detail has been sent within the cooldown period."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT 1 FROM alert_log 
            WHERE alert_type = ? AND detail = ? 
            AND sent_at > datetime('now', '-' || ? || ' minutes')
            LIMIT 1
        ''', (alert_type, detail, minutes)) as cursor:
            row = await cursor.fetchone()
            return bool(row)

async def log_alert(alert_type: str, detail: str):
    """Log that an alert has been sent."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO alert_log (alert_type, detail) 
            VALUES (?, ?)
        ''', (alert_type, detail))
        await db.commit()
