import discord
from discord.ext import commands
from discord import app_commands
import time
from config import MODELS, ALLOWED_USER_ID
from database import get_setting, set_setting
from utils.logger import logger

class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Ensure only the owner can use these commands
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != ALLOWED_USER_ID:
            await interaction.response.send_message("You are not authorized to use this bot.", ephemeral=True)
            return False
        return True

    @app_commands.command(name="ping", description="Check bot latency and online status")
    async def ping(self, interaction: discord.Interaction):
        start_time = time.time()
        await interaction.response.send_message("Pinging...")
        end_time = time.time()
        
        api_latency = round(self.bot.latency * 1000)
        msg_latency = round((end_time - start_time) * 1000)
        
        await interaction.edit_original_response(
            content=f"🏓 Pong!\n**API Latency:** {api_latency}ms\n**Message Latency:** {msg_latency}ms"
        )

    @app_commands.command(name="setmodel", description="Change the default LLM model")
    @app_commands.describe(model="The model to use as default")
    @app_commands.choices(model=[
        app_commands.Choice(name="Gemini (Google)", value="gemini"),
        app_commands.Choice(name="Groq (Llama 3.3)", value="groq"),
        app_commands.Choice(name="Claude (Anthropic)", value="claude")
    ])
    async def setmodel(self, interaction: discord.Interaction, model: app_commands.Choice[str]):
        new_model = model.value
        await set_setting('default_model', new_model)
        
        logger.info(f"Default model changed to {new_model} by user {interaction.user.id}")
        await interaction.response.send_message(f"✅ Default model successfully set to **{model.name}** (`{new_model}`).")

    @app_commands.command(name="modelinfo", description="Show the currently active default model")
    async def modelinfo(self, interaction: discord.Interaction):
        current_model = await get_setting('default_model')
        if not current_model:
            current_model = "gemini" # Fallback
            
        model_id = MODELS.get(current_model, "Unknown")
        
        await interaction.response.send_message(
            f"ℹ️ **Current Default Model**\n"
            f"- **Alias:** `{current_model}`\n"
            f"- **Model ID:** `{model_id}`\n\n"
            f"*You can temporarily override this by starting your message with `@gemini`, `@groq`, or `@claude`.*"
        )

    @app_commands.command(name="help", description="Show all available commands")
    async def help_cmd(self, interaction: discord.Interaction):
        help_text = """
**🤖 Discord VPS Agent Help**

**💬 AI Chat**
- Just type in a thread or channel to chat with the default AI.
- Prefix with `@gemini`, `@groq`, or `@claude` to force a specific model.
- `/newchat` — Create a new thread for a clean conversation context.
- `/clearchat` — Clear the history of the current thread.

**⚙️ Settings**
- `/setmodel [model]` — Change the default AI model.
- `/modelinfo` — View current model info.
- `/ping` — Check bot latency.

**🖥️ VPS Management**
- `/status` — View VPS RAM, Disk, CPU, and Uptime.
- `/services` — List systemd and PM2 services.
- `/logs [service] [lines]` — Tail logs for a service.
- `/restart [service]` — Restart a systemd/PM2 service.
- `/install [package]` — Install an apt package.
- `/exec [command]` — Run a shell command (has tier-based safety classification).

**🛡️ Pentest (Use with caution)**
- `/pentest run` — Run full pentest workflow.
- `/pentest recon` — Run only the recon phase.
- `/pentest report` — Generate the last pentest report.

*Note: The bot also monitors the VPS and will alert you in the designated channel if resources are critical.*
"""
        await interaction.response.send_message(help_text)

async def setup(bot: commands.Bot):
    # Register the Cog check globally for this cog
    cog = Settings(bot)
    # Applying the interaction check to all app commands in this cog
    for command in cog.walk_app_commands():
        command.add_check(cog.interaction_check)
    await bot.add_cog(cog)
