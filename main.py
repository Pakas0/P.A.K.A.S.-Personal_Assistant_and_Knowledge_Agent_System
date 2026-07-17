import discord
from discord.ext import commands
import os
import asyncio
from config import DISCORD_TOKEN, DISCORD_GUILD_ID
from utils.logger import logger
from database import init_db

class VPSAgentBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # Initialize Database
        await init_db()
        
        # Load Cogs
        # We will attempt to load all cogs. If some are not created yet, it will warn and continue.
        cogs = ['cogs.settings', 'cogs.chat', 'cogs.vps', 'cogs.pentest', 'monitor']
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension {cog}")
            except Exception as e:
                logger.warning(f"Failed to load extension {cog}: {e}")

        # Sync slash commands to the specific guild
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Synced slash commands to guild {DISCORD_GUILD_ID}")
        else:
            await self.tree.sync()
            logger.info("Synced slash commands globally")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("Bot is ready and listening for commands.")

def main():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN is missing in environment variables.")
        return

    bot = VPSAgentBot()
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
