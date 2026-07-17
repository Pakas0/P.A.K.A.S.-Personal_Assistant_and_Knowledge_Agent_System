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
        
        try:
            from database import get_setting
            hour_str = await get_setting('daily_digest_hour_utc')
            hour = int(hour_str) if hour_str else 0
        except Exception as e:
            logger.warning(f"Failed to load daily digest hour, defaulting to 0: {e}")
            hour = 0
            
        from utils.scheduler import register_daily_task
        from utils.digest import generate_daily_digest
        
        async def run_digest():
            await generate_daily_digest(self)
            
        self.digest_task = register_daily_task(self, hour=hour, minute=0, coro_func=run_digest)
        logger.info(f"Registered daily digest cron at {hour}:00 UTC")
        
        from utils.cleanup import cleanup_stale_exports
        
        async def run_cleanup():
            await cleanup_stale_exports(max_age_hours=1)
            
        # Register cleanup to run daily at hour + 1 just as an example, 
        # or we could register it to run multiple times, but register_daily_task runs once a day.
        # Given it's a backup mechanism, running it once a day at 1 AM UTC is fine.
        self.cleanup_task = register_daily_task(self, hour=1, minute=0, coro_func=run_cleanup)
        logger.info("Registered cleanup_stale_exports cron at 1:00 UTC")

def main():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN is missing in environment variables.")
        return

    bot = VPSAgentBot()
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
