import discord
from discord.ext import commands
from discord import app_commands
import json

from config import ALLOWED_USER_ID
from executor import classify_command, execute_command, TIER_AUTO, TIER_NOTIFY, TIER_APPROVAL
from utils.approval import ApprovalView
from utils.logger import logger
from database import log_command, get_setting, save_message
from utils.llm import generate_response

class VPS(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != ALLOWED_USER_ID:
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return False
        return True

    async def _save_to_memory(self, interaction: discord.Interaction, command: str, output: str, exit_code: int):
        """Helper to save command execution into chat history memory"""
        try:
            thread_id = str(interaction.channel_id)
            history_output = output
            if len(history_output) > 1500:
                history_output = history_output[:1500] + "\n...(output truncated in memory)..."
            
            await save_message(thread_id, "user", f"[Slash Command Executed: {command}]")
            await save_message(thread_id, "assistant", f"**Command Output (Exit code {exit_code}):**\n```\n{history_output}\n```")
        except Exception as me_e:
            logger.error(f"Failed to save command to conversation memory: {me_e}")

    async def _handle_execution(self, interaction: discord.Interaction, command: str, ephemeral=False):
        """Helper to handle the tier logic and execution of a command"""
        tier = classify_command(command)
        
        if tier == TIER_AUTO:
            await interaction.response.defer(ephemeral=ephemeral)
            output, exit_code = await execute_command(command)
            await log_command(command, tier, None, output, exit_code)
            await self._save_to_memory(interaction, command, output, exit_code)
            
            # Format output
            formatted_output = f"**Executed:** `{command}`\n```\n{output[:1900]}\n```"
            if len(output) > 1900:
                formatted_output += "\n*(Output truncated)*"
            
            await interaction.followup.send(formatted_output)

        elif tier == TIER_NOTIFY:
            await interaction.response.defer(ephemeral=ephemeral)
            output, exit_code = await execute_command(command)
            await log_command(command, tier, None, output, exit_code)
            await self._save_to_memory(interaction, command, output, exit_code)
            
            formatted_output = f"⚠️ **Executed (Auto+Notify):** `{command}`\n✅ Done with exit code {exit_code}.\n```\n{output[:1800]}\n```"
            await interaction.followup.send(formatted_output)

        elif tier == TIER_APPROVAL:
            view = ApprovalView(command)
            await interaction.response.send_message(
                f"🔴 **Approval Required**\nCommand: `{command}`\n\n⚠️ This action might be destructive or require elevated privileges.\nTimeout: 60 seconds.",
                view=view
            )
            
            # Wait for button press
            await view.wait()
            
            if view.value is None:
                # Timeout
                await interaction.edit_original_response(content=f"⏳ Approval timed out for `{command}`.", view=None)
                await log_command(command, tier, False, "Timeout", -1)
            elif view.value is True:
                # Approved
                output, exit_code = await execute_command(command)
                await log_command(command, tier, True, output, exit_code)
                await self._save_to_memory(interaction, command, output, exit_code)
                
                formatted_output = f"✅ **Executed after approval:** `{command}`\n```\n{output[:1800]}\n```"
                await interaction.followup.send(formatted_output)
            else:
                # Rejected
                await log_command(command, tier, False, "Rejected by user", -1)

    @app_commands.command(name="status", description="Show VPS resource usage and uptime")
    async def status(self, interaction: discord.Interaction):
        await self._handle_execution(interaction, "free -m && echo '---' && df -h / && echo '---' && uptime")

    @app_commands.command(name="services", description="List systemd and PM2 services")
    async def services(self, interaction: discord.Interaction):
        command = "echo '=== SYSTEMD ===' && systemctl list-units --type=service --state=running | head -n 15 && echo '=== PM2 ===' && pm2 list"
        await self._handle_execution(interaction, command)

    @app_commands.command(name="logs", description="Tail logs for a service")
    @app_commands.describe(service="Service name (pm2 or systemd)", lines="Number of lines to tail")
    async def logs(self, interaction: discord.Interaction, service: str, lines: int = 50):
        # We try journalctl first, if not we try pm2 (since we can't easily know which one it is without checking)
        # Or we can just run both and one will fail silently or show error
        command = f"journalctl -u {service} -n {lines} --no-pager || pm2 logs {service} --lines {lines} --nostream"
        await self._handle_execution(interaction, command)

    @app_commands.command(name="restart", description="Restart a systemd or PM2 service")
    @app_commands.describe(service="Service name")
    async def restart(self, interaction: discord.Interaction, service: str):
        # Assuming sudo for systemd is allowed in whitelist
        command = f"sudo systemctl restart {service} || pm2 restart {service}"
        await self._handle_execution(interaction, command)

    @app_commands.command(name="install", description="Install an apt package (Tier ⚠️)")
    @app_commands.describe(package="Package name to install")
    async def install(self, interaction: discord.Interaction, package: str):
        # We use sudo because apt install requires it, assuming it's in the whitelist
        command = f"sudo apt install -y {package}"
        await self._handle_execution(interaction, command)

    @app_commands.command(name="exec", description="Execute a raw shell command")
    @app_commands.describe(command="The shell command to execute")
    async def exec_cmd(self, interaction: discord.Interaction, command: str):
        await self._handle_execution(interaction, command)
        
    @app_commands.command(name="do", description="Translate natural language to a shell command and execute it")
    @app_commands.describe(intent="What you want the VPS to do in natural language")
    async def do_cmd(self, interaction: discord.Interaction, intent: str):
        await interaction.response.defer()
        
        try:
            model_alias = await get_setting('default_model') or "gemini"
            
            system_prompt = (
                "You are an expert Linux sysadmin. The user will give you a natural language intent. "
                "Your job is to translate it into a single, valid Ubuntu Linux bash command. "
                "Output ONLY the command. Do not use markdown blocks, do not explain. "
                "Just the raw command string."
            )
            
            messages = [{"role": "user", "content": intent}]
            
            generated_command = await generate_response(model_alias, messages, system_prompt=system_prompt)
            generated_command = generated_command.strip()
            
            # Remove markdown if the LLM accidentally added it
            if generated_command.startswith("```"):
                lines = generated_command.split("\n")
                if len(lines) >= 2:
                    generated_command = "\n".join(lines[1:-1])
                    
            generated_command = generated_command.strip("`").strip()
            
            if not generated_command:
                await interaction.followup.send("❌ Failed to generate a command from that intent.")
                return
                
            await interaction.followup.send(f"🤖 **Translated Intent:**\n`{intent}`\n**Command:** `{generated_command}`\n\nProcessing execution...")
            
            # Re-fetch interaction context to handle the generated command
            # Since we already responded to the interaction, we'll need to adapt _handle_execution 
            # to not use interaction.response.defer() if it's already deferred.
            
            tier = classify_command(generated_command)
            
            if tier == TIER_AUTO or tier == TIER_NOTIFY:
                output, exit_code = await execute_command(generated_command)
                await log_command(generated_command, tier, None, output, exit_code)
                await self._save_to_memory(interaction, generated_command, output, exit_code)
                
                prefix = "⚠️ **Auto+Notify**" if tier == TIER_NOTIFY else "✅ **Auto**"
                
                formatted_output = f"{prefix}\n```\n{output[:1900]}\n```"
                await interaction.followup.send(formatted_output)
                
            elif tier == TIER_APPROVAL:
                view = ApprovalView(generated_command)
                msg = await interaction.followup.send(
                    f"🔴 **Approval Required**\n⚠️ This action might be destructive or require elevated privileges.\nTimeout: 60 seconds.",
                    view=view,
                    wait=True
                )
                
                await view.wait()
                
                if view.value is None:
                    await msg.edit(content=f"⏳ Approval timed out for `{generated_command}`.", view=None)
                    await log_command(generated_command, tier, False, "Timeout", -1)
                elif view.value is True:
                    output, exit_code = await execute_command(generated_command)
                    await log_command(generated_command, tier, True, output, exit_code)
                    await self._save_to_memory(interaction, generated_command, output, exit_code)
                    await msg.reply(f"✅ **Executed:**\n```\n{output[:1900]}\n```")
                else:
                    await log_command(generated_command, tier, False, "Rejected by user", -1)
                    
        except Exception as e:
            logger.error(f"Error in natural language translation: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}")

async def setup(bot: commands.Bot):
    cog = VPS(bot)
    for command in cog.walk_app_commands():
        command.add_check(cog.interaction_check)
    await bot.add_cog(cog)
