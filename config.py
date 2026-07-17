import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Discord settings
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")

# Convert IDs to int if they exist
if DISCORD_GUILD_ID:
    DISCORD_GUILD_ID = int(DISCORD_GUILD_ID)
if ALLOWED_USER_ID:
    ALLOWED_USER_ID = int(ALLOWED_USER_ID)
if ALERT_CHANNEL_ID:
    ALERT_CHANNEL_ID = int(ALERT_CHANNEL_ID)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Optional Proxy URL
NINER_ROUTER_URL = os.getenv("NINER_ROUTER_URL")

# Application Default Settings
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini")

# Model List (Aliases and their actual API names)
MODELS = {
    "gemini": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "claude": "claude-3-5-haiku-20241022",
}

# Directories and Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "memory.db")
