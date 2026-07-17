import discord
from discord.ext import commands
from discord import app_commands
import datetime
from config import ALLOWED_USER_ID, MODELS
from database import get_setting, get_history, save_message, clear_history
from utils.logger import logger
from utils.llm import generate_response

class Chat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != ALLOWED_USER_ID:
            await interaction.response.send_message("You are not authorized to use this bot.", ephemeral=True)
            return False
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and unauthorized users
        if message.author.bot or message.author.id != ALLOWED_USER_ID:
            return

        # We don't process messages starting with '/' (slash commands) though Discord 
        # handles slash commands before on_message anyway. But if user types a normal 
        # prefix command by accident, we can choose to process it as chat or ignore.
        
        content = message.content.strip()
        if not content:
            return

        model_alias = await get_setting('default_model')
        if not model_alias:
            model_alias = "gemini"
            
        override_used = False
        
        # Detect prefix to override model for this message only dynamically
        lower_content = content.lower()
        for alias in MODELS.keys():
            prefix = f"@{alias}"
            if lower_content.startswith(prefix):
                model_alias = alias
                content = content[len(prefix):].strip()
                override_used = True
                break
            
        # Read attachments if any (text-based files up to 100KB)
        attachment_text = ""
        if message.attachments:
            for attachment in message.attachments:
                is_text = False
                exts = ('.txt', '.py', '.js', '.json', '.md', '.log', '.env', '.yaml', '.yml', '.ini', '.cfg', '.conf', '.sh', '.bash', '.ts', '.tsx', '.html', '.css')
                if attachment.filename.lower().endswith(exts):
                    is_text = True
                elif attachment.content_type and (attachment.content_type.startswith('text/') or attachment.content_type == 'application/json'):
                    is_text = True
                
                if is_text:
                    if attachment.size > 100 * 1024:  # 100 KB limit
                        attachment_text += f"\n\n[Attachment {attachment.filename} is too large and was skipped (Max: 100KB)]"
                        continue
                    try:
                        file_bytes = await attachment.read()
                        file_text = file_bytes.decode('utf-8', errors='ignore')
                        attachment_text += f"\n\n--- Attachment: {attachment.filename} ---\n{file_text}\n-----------------------"
                    except Exception as attr_e:
                        logger.error(f"Failed to read attachment {attachment.filename}: {attr_e}")
                        attachment_text += f"\n\n[Error reading attachment: {attachment.filename}]"
        
        combined_content = content
        if attachment_text:
            combined_content += attachment_text

        if not combined_content:
            # If the user only sent "@alias " with no content and no readable attachments
            return

        thread_id = str(message.channel.id)
        
        async with message.channel.typing():
            try:
                # Fetch history (last 20 messages)
                history = await get_history(thread_id, limit=20)
                
                messages = history.copy()
                messages.append({"role": "user", "content": combined_content})
                
                system_prompt = "You are P.A.K.A.S, a personal AI assistant and VPS manager for your owner. You are running as a Discord bot. Be helpful, concise, and technical."
                
                response_text = await generate_response(model_alias, messages, system_prompt=system_prompt)
                
                # Save to DB
                await save_message(thread_id, "user", combined_content, model_alias if override_used else None)
                await save_message(thread_id, "assistant", response_text, model_alias)
                
                # Send response (split if > 2000 chars to avoid Discord limits)
                if len(response_text) > 2000:
                    # Very simple chunking
                    chunks = [response_text[i:i+1950] for i in range(0, len(response_text), 1950)]
                    for chunk in chunks:
                        await message.channel.send(chunk)
                else:
                    await message.reply(response_text)
                    
            except Exception as e:
                logger.error(f"Chat error: {str(e)}")
                await message.reply(f"❌ Error generating response: {str(e)}")

    @app_commands.command(name="newchat", description="Create a new thread for a fresh conversation")
    async def newchat(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("This command can only be used in a regular text channel.", ephemeral=True)
            return
            
        thread_name = f"Chat - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
        thread = await interaction.channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.public_thread,
            auto_archive_duration=1440 # 24 hours
        )
        
        await interaction.response.send_message(f"✅ Created new chat thread: {thread.mention}")
        await thread.send("Hello! This is a new conversation thread. The context is fresh and empty. What would you like to discuss?")

    @app_commands.command(name="clearchat", description="Clear the conversation history for the current thread/channel")
    async def clearchat(self, interaction: discord.Interaction):
        thread_id = str(interaction.channel_id)
        await clear_history(thread_id)
        await interaction.response.send_message("🧹 Conversation history for this thread has been cleared.")

async def setup(bot: commands.Bot):
    cog = Chat(bot)
    for command in cog.walk_app_commands():
        command.add_check(cog.interaction_check)
    await bot.add_cog(cog)
