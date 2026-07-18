import discord
from discord.ext import commands
from discord import app_commands
import datetime
from config import ALLOWED_USER_ID, MODELS
from database import get_setting, get_history, save_message, clear_history
from utils.logger import logger
from utils.llm import generate_response, call_llm_with_tools
from utils.formatter import send_long_response
from utils.summarizer import maybe_summarize_thread

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
                # 1. Summarize if needed before fetching history
                await maybe_summarize_thread(thread_id, threshold=30)
                
                # Fetch history (last 20 messages)
                history = await get_history(thread_id, limit=20)
                
                messages = history.copy()
                messages.append({"role": "user", "content": combined_content})
                
                system_prompt = (
                    "You are P.A.K.A.S, a personal AI assistant and VPS manager for Bagaskara (Owner). You are running as a Discord bot. "
                    "Be helpful, concise, and technical. "
                    "IMPORTANT INSTRUCTIONS: You have access to tools (functions) to help you perform tasks. You have maximum of 6x iteration, be carefull what you do and what you say. "
                    "You have access to `execute_shell_command` for running commands on the user's VPS. Only use "
                    "this tool when the user's message clearly expresses intent related to VPS/server operations — "
                    "for example: checking status/resources (RAM, disk, CPU), viewing logs, checking running "
                    "services/processes, restarting a service, or diagnosing a problem with the server/Markify/PM2. "
                    "Do NOT use this tool for: "
                    "- General conversation, questions unrelated to the VPS/server "
                    "- Ambiguous requests where VPS intent is not clearly stated "
                    "- Hypothetical or explanatory questions ('how would I check RAM usage?' is a question about "
                    "HOW, not a request to actually run it — answer in text unless the user's phrasing clearly "
                    "asks you to check it now). "
                    "When VPS intent IS clear, call the tool directly without asking for permission first (the "
                    "tier/approval system in the tool itself will handle safety — you don't need to ask separately). "
                    "If in doubt whether the user wants you to actually run something vs. just explain, prefer "
                    "asking a short clarifying question in text rather than guessing and executing. "
                    "If the user asks you to search the web, use the `web_search` tool. "
                    "If the user asks to generate a document, use the `generate_document` tool. "
                    "If the conversation history shows a recent message starting with '⚠️ Task belum selesai dalam' "
                    "followed by a numbered list of steps already attempted, and the user's new message is short and "
                    "generic (e.g. 'lanjutkan', 'terusin', 'lanjut', 'continue', 'coba lagi'), treat this as a "
                    "request to CONTINUE the incomplete task — not a new question. Review what was already "
                    "attempted in the progress list, avoid repeating the exact same tool calls that already "
                    "succeeded, and proceed toward completing the original request."
                )
                
                # Use call_llm_with_tools to handle tool calls
                response_text, generated_files = await call_llm_with_tools(model_alias, messages, thread_id, system_prompt, max_iterations=6, message_obj=message)
                
                # Save to DB
                await save_message(thread_id, "user", combined_content, model_alias if override_used else None)
                await save_message(thread_id, "assistant", response_text, model_alias)
                
                # Send response via formatter
                await send_long_response(message, response_text, tldr_threshold=1500, model_alias=model_alias, file_paths=generated_files)
                    
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
