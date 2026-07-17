import discord
from discord.ext import commands, tasks
import psutil
import asyncio
import json
from config import ALERT_CHANNEL_ID
from database import is_alert_on_cooldown, log_alert
from utils.logger import logger

class Monitor(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.monitoring_task.start()

    def cog_unload(self):
        self.monitoring_task.cancel()

    @tasks.loop(minutes=5.0)
    async def monitoring_task(self):
        await self.bot.wait_until_ready()
        
        if not ALERT_CHANNEL_ID:
            return
            
        channel = self.bot.get_channel(ALERT_CHANNEL_ID)
        if not channel:
            logger.warning(f"Alert channel {ALERT_CHANNEL_ID} not found.")
            return

        if not isinstance(channel, discord.abc.Messageable):
            logger.error(f"Alert channel {ALERT_CHANNEL_ID} is not a text channel or thread (type: {type(channel).__name__}). Alerts cannot be sent.")
            return

        try:
            # RAM Check
            ram = psutil.virtual_memory()
            if ram.percent > 90:
                if not await is_alert_on_cooldown('ram', 'high_usage', 30):
                    desc = f"RAM usage is at {ram.percent}%\n({ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB)"
                    
                    # Get top processes by memory
                    try:
                        procs = sorted(psutil.process_iter(['name', 'memory_info']), key=lambda p: p.info['memory_info'].rss, reverse=True)[:3]
                        desc += "\n\nTop processes by RAM:\n"
                        for p in procs:
                            desc += f"- {p.info['name']} — {p.info['memory_info'].rss // (1024**2)}MB\n"
                    except Exception as e:
                        logger.error(f"Error getting top processes: {e}")
                        
                    await self.send_alert(channel, "RAM Critical", desc)
                    await log_alert('ram', 'high_usage')

            # Disk Check
            disk = psutil.disk_usage('/')
            if disk.percent > 85:
                if not await is_alert_on_cooldown('disk', 'high_usage', 30):
                    desc = f"Disk usage is at {disk.percent}%\n({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"
                    await self.send_alert(channel, "Disk Critical", desc)
                    await log_alert('disk', 'high_usage')

            # Services Check (systemd)
            services_to_check = ['nginx', 'cloudflared']
            for service in services_to_check:
                process = await asyncio.create_subprocess_shell(
                    f"systemctl is-active {service}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await process.communicate()
                if stdout.decode().strip() != "active":
                    if not await is_alert_on_cooldown('service_down', service, 30):
                        await self.send_alert(channel, f"Service Down: {service}", f"The systemd service `{service}` is not active.")
                        await log_alert('service_down', service)

            # PM2 Check
            pm2_services = ['markify-backend', 'markify-frontend']
            process = await asyncio.create_subprocess_shell(
                f"pm2 jlist",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            
            try:
                output = stdout.decode().strip()
                if output:
                    pm2_data = json.loads(output)
                    for service in pm2_services:
                        is_online = False
                        for app in pm2_data:
                            if app.get('name') == service and app.get('pm2_env', {}).get('status') == 'online':
                                is_online = True
                                break
                        if not is_online:
                             if not await is_alert_on_cooldown('service_down', service, 30):
                                await self.send_alert(channel, f"Service Down: {service}", f"The PM2 service `{service}` is not online.")
                                await log_alert('service_down', service)
            except Exception as e:
                logger.error(f"Error parsing pm2 jlist output: {e}")
                
        except Exception as e:
            logger.error(f"Error in monitoring task: {e}")


    async def send_alert(self, channel, title, description):
        embed = discord.Embed(title=f"⚠️ ALERT — {title}", description=description, color=discord.Color.red())
        import datetime
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Monitor(bot))
