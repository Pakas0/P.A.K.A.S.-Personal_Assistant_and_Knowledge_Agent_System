import datetime
from discord.ext import tasks
from utils.logger import logger

def register_daily_task(bot, hour: int, minute: int, coro_func):
    """
    Daftarkan task yang jalan sekali sehari di jam:menit tertentu (UTC).
    coro_func: async function tanpa argumen yang akan dipanggil.
    """
    @tasks.loop(time=datetime.time(hour=hour, minute=minute))
    async def _task():
        try:
            await coro_func()
        except Exception as e:
            logger.error(f"Scheduled task error: {e}")
    
    @_task.before_loop
    async def before_task():
        await bot.wait_until_ready()
        
    _task.start()
    return _task
