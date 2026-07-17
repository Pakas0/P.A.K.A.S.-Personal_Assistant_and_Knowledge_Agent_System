import asyncio
import discord
from utils.logger import logger
from utils.llm import generate_response
from database import get_setting

TIER_AUTO = "auto"
TIER_NOTIFY = "notify"
TIER_APPROVAL = "approval"

def classify_command(command: str) -> str:
    """
    Classify a shell command into execution tiers.
    Default to TIER_APPROVAL if not explicitly matched (fail-safe).
    """
    cmd = command.strip().lower()

    # Tier 🔴 — DANGEROUS (Requires Approval)
    DANGEROUS_PATTERNS = [
        "rm -rf", "rm -f", "shred", "truncate",
        "chmod 777", "chmod -r", "chown root",
        "systemctl stop", "systemctl disable",
        "pm2 delete",
        "reboot", "shutdown", "poweroff",
        "dd if=", "mkfs", "fdisk", "parted",
        "ufw reset", "iptables -f",
        "drop table", "drop database", "delete from",
        "crontab -r",
        "apt remove nginx", "apt remove python3", "apt purge",
    ]
    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd:
            return TIER_APPROVAL

    # Tier ⚠️ — NOTIFY (Auto Execute + Notify)
    NOTIFY_PATTERNS = [
        "apt install", "apt update", "apt remove",
        "pip install", "npm install",
        "git pull", "git fetch", "git checkout",
        "mkdir", "cp ", "mv ", "touch ",
        "nano ", "vim ",
        "pm2 restart", "pm2 start", "pm2 stop",
        "systemctl restart", "systemctl start", "systemctl reload",
        "cloudflared",
    ]
    for pattern in NOTIFY_PATTERNS:
        if pattern in cmd:
            return TIER_NOTIFY

    # Tier ✅ — AUTO (Safe / Read-only)
    SAFE_PATTERNS = [
        "ls", "cat", "head", "tail", "grep", "find", "locate",
        "df", "du", "free", "top", "htop", "ps", "uptime", "env", "printenv", "echo",
        "systemctl status", "pm2 status", "pm2 list", "pm2 logs",
        "git status", "git log", "git diff", "git branch",
        "curl", "wget --spider", "ping", "netstat", "ss", "nslookup", "dig", "whois",
        "journalctl", "uname", "whoami", "id", "pwd", "nginx -t"
    ]
    
    # Needs to match prefix or word boundary to prevent accidental matching
    # e.g., 'cat' should match 'cat file' but not 'locate' (handled by starting with or space before)
    for pattern in SAFE_PATTERNS:
        if cmd.startswith(pattern) or f" {pattern}" in cmd:
            return TIER_AUTO

    # Fail-safe: If it doesn't match any safe/notify patterns, require approval
    return TIER_APPROVAL

async def execute_command(command: str) -> tuple[str, int]:
    """
    Execute a shell command asynchronously and return (output, exit_code).
    """
    logger.info(f"Executing shell command: {command}")
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        output = stdout.decode('utf-8').strip()
        err_output = stderr.decode('utf-8').strip()
        
        # Combine stdout and stderr if both exist, otherwise take whichever has content
        final_output = ""
        if output and err_output:
            final_output = f"STDOUT:\n{output}\n\nSTDERR:\n{err_output}"
        elif err_output:
            final_output = err_output
        else:
            final_output = output
            
        if not final_output and process.returncode == 0:
            final_output = "Command executed successfully with no output."
            
        return final_output, process.returncode
    except Exception as e:
        logger.error(f"Error executing command '{command}': {str(e)}")
        return f"Exception occurred: {str(e)}", -1

async def maybe_explain_error(command: str, output: str, exit_code: int, channel: discord.abc.Messageable):
    """
    Called after execution if exit_code != 0.
    Fetches explanation from LLM and sends it to the same channel.
    """
    if exit_code == 0:
        return
        
    try:
        trunc_output = output
        if len(trunc_output) > 1000:
            trunc_output = trunc_output[:1000] + "..."
            
        prompt = (
            f"Perintah VPS gagal dieksekusi:\n"
            f"Command: {command}\n"
            f"Exit Code: {exit_code}\n"
            f"Output:\n{trunc_output}\n\n"
            f"Berikan penjelasan singkat tentang kemungkinan penyebab error ini dan saran perbaikannya."
        )
        
        model_alias = await get_setting('default_model') or "gemini"
        
        explanation = await generate_response(
            model_alias, 
            [{"role": "user", "content": prompt}], 
            system_prompt="Anda adalah asisten DevOps. Jawab dengan singkat, jelas, dan fokus pada solusi."
        )
        
        await channel.send(f"💡 **AI Error Explanation:**\n{explanation}")
    except Exception as e:
        logger.error(f"Error generating error explanation: {e}")
