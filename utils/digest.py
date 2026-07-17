import aiosqlite
import discord
from config import DB_PATH, DIGEST_CHANNEL_ID
from utils.logger import logger
from utils.llm import generate_response
from database import get_setting

async def generate_daily_digest(bot: discord.Client):
    """
    Generate daily VPS health digest using data from alert_log, command_history,
    and vps_snapshots (if added).
    """
    enabled = await get_setting('daily_digest_enabled')
    if enabled != 'true':
        return
        
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            # Get alerts from last 24h
            async with db.execute('''
                SELECT alert_type, detail, sent_at FROM alert_log 
                WHERE sent_at > datetime('now', '-1 day')
                ORDER BY id ASC
            ''') as cursor:
                alerts = await cursor.fetchall()
                
            # Get commands from last 24h
            async with db.execute('''
                SELECT command, tier, exit_code, executed_at FROM command_history 
                WHERE executed_at > datetime('now', '-1 day')
                ORDER BY id ASC
            ''') as cursor:
                commands = await cursor.fetchall()
                
            # Get latest snapshot
            async with db.execute('''
                SELECT snapshot, created_at FROM vps_snapshots 
                ORDER BY id DESC LIMIT 1
            ''') as cursor:
                snapshot = await cursor.fetchone()
                
        # Format for LLM
        prompt = "Berikan rangkuman Daily VPS Health Digest (insight kesehatan VPS, potensi masalah, & ringkasan operasi harian) berdasarkan data 24 jam terakhir ini:\n\n"
        
        if snapshot:
            prompt += f"LATEST SNAPSHOT ({snapshot['created_at']}):\n{snapshot['snapshot']}\n\n"
            
        prompt += f"ALERTS IN LAST 24H: {len(alerts)}\n"
        for a in alerts:
            prompt += f"- [{a['sent_at']}] {a['alert_type']}: {a['detail']}\n"
            
        prompt += f"\nCOMMANDS EXECUTED IN LAST 24H: {len(commands)}\n"
        for c in commands:
            prompt += f"- [{c['executed_at']}] {c['command']} (Exit: {c['exit_code']})\n"
            
        model_alias = await get_setting('default_model') or "gemini"
        
        digest_text = await generate_response(model_alias, [{"role": "user", "content": prompt}], system_prompt="Anda adalah asisten DevSecOps. Berikan insight ringkas tentang stabilitas sistem, penggunaan command, dan apa yang perlu diperhatikan hari ini.")
        
        # Send to channel
        channel = bot.get_channel(int(DIGEST_CHANNEL_ID))
        if channel:
            if len(digest_text) > 2000:
                chunks = [digest_text[i:i+1950] for i in range(0, len(digest_text), 1950)]
                for chunk in chunks:
                    await channel.send(chunk)
            else:
                await channel.send(f"📊 **Daily VPS Digest**\n\n{digest_text}")
                
    except Exception as e:
        logger.error(f"Error generating daily digest: {e}")
