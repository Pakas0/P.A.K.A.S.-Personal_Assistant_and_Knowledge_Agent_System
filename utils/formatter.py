import os
import discord
from utils.logger import logger
from utils.llm import generate_response
from database import get_setting

async def send_long_response(message: discord.Message, text: str, tldr_threshold: int = 1500, model_alias: str = None, file_paths: list[str] = None):
    """
    1. If len(text) <= 2000: send directly.
    2. If > 2000: split into messages
    3. If > tldr_threshold: generate TL;DR first via LLM.
    """
    try:
        discord_files = []
        if file_paths:
            for path in file_paths:
                if os.path.exists(path) and os.path.getsize(path) < 20 * 1024 * 1024:
                    discord_files.append(discord.File(path))
                    
        if len(text) <= 2000:
            if discord_files:
                await message.reply(text, files=discord_files)
            else:
                await message.reply(text)
            _cleanup_files(file_paths)
            return
            
        if len(text) > tldr_threshold:
            # Generate TL;DR
            logger.info("Generating TL;DR for long response...")
            if not model_alias:
                model_alias = await get_setting('default_model') or "gemini"
                
            tldr_prompt = f"Berikan 1-2 kalimat singkat TL;DR untuk teks berikut:\n\n{text[:3000]}..."
            tldr = await generate_response(model_alias, [{"role": "user", "content": tldr_prompt}])
            await message.reply(f"📌 **TL;DR:** {tldr}\n\n*Full response below:*")
            
        # Split text carefully at newlines if possible
        chunks = []
        current_chunk = ""
        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 > 1950:
                chunks.append(current_chunk)
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        if current_chunk:
            chunks.append(current_chunk)
            
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                if i == len(chunks) - 1 and discord_files:
                    await message.channel.send(chunk, files=discord_files)
                else:
                    await message.channel.send(chunk)
                    
        _cleanup_files(file_paths)
                
    except Exception as e:
        logger.error(f"Error sending long response: {e}")
        await message.reply("❌ Error sending long response.")

def _cleanup_files(file_paths: list[str]):
    if not file_paths:
        return
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.error(f"Error deleting file {path}: {e}")
