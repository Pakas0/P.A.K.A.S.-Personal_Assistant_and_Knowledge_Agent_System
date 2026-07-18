import os
import json
import logging
from config import GEMINI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY, NINER_ROUTER_URL, MODELS
from utils.search import web_search
from utils.documents import generate_document
from executor import classify_command, execute_command, TIER_APPROVAL
from database import save_tool_call, save_tool_result, log_command

logger = logging.getLogger("discord_agent")

WEB_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Cari informasi terkini di internet. Gunakan untuk pertanyaan tentang harga, berita, dokumentasi terbaru, atau fakta yang mungkin berubah setelah training data model.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Kata kunci pencarian"},
                "max_results": {"type": "integer", "description": "Jumlah hasil (default 5)"}
            },
            "required": ["query"]
        }
    }
}

GENERATE_DOCUMENT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_document",
        "description": "Buat file dokumen (docx, xlsx, pptx, atau pdf) dari konten yang diminta user, lalu kirim sebagai attachment Discord. Gunakan saat user secara eksplisit minta laporan/dokumen/file dalam format tertentu.",
        "parameters": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["docx", "xlsx", "pptx", "pdf"],
                    "description": "Format file yang diminta"
                },
                "title": {
                    "type": "string",
                    "description": "Judul dokumen/laporan"
                },
                "sections": {
                    "type": "array",
                    "description": "Untuk format docx/pdf/pptx: list bagian dengan heading dan content. Untuk xlsx: gunakan field 'table_data' sebagai gantinya.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "content": {"type": "string"}
                        }
                    }
                },
                "table_data": {
                    "type": "object",
                    "description": "Khusus format xlsx: {\"headers\": [...], \"rows\": [[...], ...]}",
                    "properties": {
                        "headers": {"type": "array", "items": {"type": "string"}},
                        "rows": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "required": ["format", "title"]
        }
    }
}

EXECUTE_COMMAND_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_shell_command",
        "description": "Jalankan perintah shell/bash di VPS secara otonom. Gunakan ini jika user meminta untuk mengecek resource (RAM/Disk), melihat isi direktori, membaca file log, dsb. PERINGATAN: Jangan gunakan untuk perintah destruktif (rm, apt, reboot, dll) karena akan ditolak otomatis oleh sistem keamanan.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Perintah bash yang ingin dieksekusi (misal: 'free -m', 'ls -la', 'cat /var/log/syslog')"
                }
            },
            "required": ["command"]
        }
    }
}

async def generate_response(model_alias: str, messages: list[dict], system_prompt: str = None) -> str:
    """
    Generate a response from the specified LLM.
    messages format: [{"role": "user"/"assistant", "content": "..."}]
    """
    if model_alias not in MODELS:
        raise ValueError(f"Unknown model alias: {model_alias}")
    
    model_id = MODELS[model_alias]
    
    # Determine if we should use direct SDK or proxy mode
    use_proxy = False
    if NINER_ROUTER_URL:
        # Check if we have native keys to bypass the proxy
        if model_alias == "gemini" and GEMINI_API_KEY:
            use_proxy = False
        elif model_alias == "claude" and ANTHROPIC_API_KEY:
            use_proxy = False
        # Note: Groq is routed through proxy if NINER_ROUTER_URL is present, due to VPS geoblocking
        else:
            use_proxy = True

    try:
        if use_proxy:
            logger.info(f"Using proxy mode (NINER_ROUTER_URL) for {model_alias}")
            return await _generate_via_proxy(model_id, messages, system_prompt)
        else:
            logger.info(f"Using direct SDK mode for {model_alias}")
            if model_alias == "gemini":
                return await _generate_gemini(model_id, messages, system_prompt)
            elif model_alias == "groq":
                return await _generate_groq(model_id, messages, system_prompt)
            elif model_alias == "claude":
                return await _generate_claude(model_id, messages, system_prompt)
            else:
                raise ValueError(f"Direct SDK not implemented for {model_alias}")
    except Exception as e:
        logger.error(f"Error generating response from {model_alias}: {str(e)}")
        raise

async def call_llm_with_tools(model_alias: str, messages: list[dict], thread_id: str, system_prompt: str = None, max_iterations: int = 6, message_obj = None) -> tuple[str, list[str]]:
    """
    Wrapper around generate_response to handle tool calling loop.
    Uses text-based tool emulation for all models to ensure universal compatibility.
    The model responds with a ```tool_call``` JSON block which we parse and execute.
    Returns (response_text, list_of_file_paths)
    """
    iteration = 0
    current_messages = messages.copy()
    generated_files = []
    
    # Build tool emulation system prompt suffix
    TOOL_EMULATION_INSTRUCTIONS = """

## TOOLS
You have these tools. To call one, output ONLY the JSON block below — no text before or after it:

```tool_call
{"tool": "<name>", "args": {<args>}}
```

Tools:
- execute_shell_command(command) → run bash on the VPS. Chain commands with && to minimize round-trips (e.g. "pm2 list && free -m").
- web_search(query, max_results=5) → search the web.
- generate_document(format, title, sections, table_data) → create docx/xlsx/pptx/pdf.

## STRICT RULES
1. NEVER output any text before the ```tool_call``` block — call the tool immediately.
2. Combine related shell checks into ONE command using && to save iterations.
3. After receiving a [Tool Result], respond in plain text — do NOT call another tool unless absolutely necessary.
4. If no tool is needed, reply normally without any JSON block.
"""
    
    indicator_msg = None
    if message_obj:
        indicator_msg = await message_obj.reply("🤔 Thinking...")
    
    while iteration < max_iterations:
        iteration += 1
        
        
        # --- Text-based Tool Emulation (works for ALL providers) ---
        # Build augmented system prompt
        augmented_system = (system_prompt or "") + TOOL_EMULATION_INSTRUCTIONS
        
        # Flatten all messages (including tool history) to plain user/assistant pairs
        flat_messages = []
        for m in current_messages:
            if m["role"] == "tool_call":
                flat_messages.append({
                    "role": "assistant",
                    "content": f"```tool_call\n{{\"tool\": \"{m.get('tool_name')}\", \"args\": {m.get('content')}}}\n```"
                })
            elif m["role"] == "tool_result":
                content = m.get("content", "")
                if len(content) > 2000:
                    content = content[:2000] + "...(truncated)"
                flat_messages.append({
                    "role": "user",
                    "content": f"**[Tool Result: {m.get('tool_name')}]**\n{content}"
                })
            else:
                flat_messages.append({"role": m["role"], "content": m["content"]})
        
        try:
            raw_response = await generate_response(model_alias, flat_messages, augmented_system)
        except Exception as e:
            if indicator_msg:
                try:
                    await indicator_msg.delete()
                except Exception:
                    pass
            raise
        
        # Check if model wants to call a tool
        tool_call_req = _parse_tool_call_from_text(raw_response)
        
        if tool_call_req:
            func_name = tool_call_req.get("tool")
            func_args_dict = tool_call_req.get("args", {})
            func_args_str = json.dumps(func_args_dict)
            
            logger.info(f"[Emulated tool call] {func_name}({func_args_str})")
            await save_tool_call(thread_id, func_name, func_args_str, model_alias)
            
            res_str, file_path = await _execute_tool(func_name, func_args_str, indicator_msg)
            if file_path:
                generated_files.append(file_path)
            
            if len(res_str) > 3000:
                res_str = res_str[:3000] + "...(truncated)"
            await save_tool_result(thread_id, func_name, res_str, model_alias)
            
            current_messages.append({"role": "tool_call", "content": func_args_str, "tool_name": func_name})
            current_messages.append({"role": "tool_result", "content": res_str, "tool_name": func_name})
            # Continue loop so model sees the result and can compose final answer
        else:
            # No tool call → final response
            if indicator_msg:
                try:
                    await indicator_msg.delete()
                except Exception:
                    pass
            return raw_response, generated_files
    
    if indicator_msg:
        try:
            await indicator_msg.delete()
        except Exception:
            pass
    return "⚠️ Terlalu banyak iterasi. Silakan coba lagi.", generated_files


def _parse_tool_call_from_text(text: str) -> dict | None:
    """Parse a ```tool_call ... ``` JSON block from model response text."""
    import re
    pattern = r"```tool_call\s*(\{.*?\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


async def _execute_tool(func_name: str, func_args_str: str, indicator_msg=None) -> tuple[str, str | None]:
    """Execute a named tool and return (result_str, file_path_or_None)."""
    file_path = None
    try:
        args = json.loads(func_args_str)
    except Exception:
        args = {}
    
    if func_name == "web_search":
        if indicator_msg:
            try:
                await indicator_msg.edit(content=f"🔍 Searching: \"{args.get('query', '...')}\"...")
            except Exception:
                pass
        try:
            res = await web_search(args.get("query", ""), args.get("max_results", 5))
            res_str = json.dumps(res)
        except Exception as e:
            res_str = json.dumps({"error": str(e)})
            
    elif func_name == "generate_document":
        if indicator_msg:
            try:
                await indicator_msg.edit(content=f"📄 Membuat dokumen {args.get('format', '')}...")
            except Exception:
                pass
        try:
            res = await generate_document(
                args.get("format"),
                args.get("title"),
                args.get("sections"),
                args.get("table_data")
            )
            res_str = json.dumps(res)
            if "file_path" in res:
                file_path = res["file_path"]
        except Exception as e:
            res_str = json.dumps({"error": str(e)})
            
    elif func_name == "execute_shell_command":
        cmd = args.get("command", "")
        if indicator_msg:
            try:
                await indicator_msg.edit(content=f"💻 Mengeksekusi: `{cmd}`...")
            except Exception:
                pass
        try:
            tier = classify_command(cmd)
            if tier == TIER_APPROVAL:
                res_str = json.dumps({"error": "Perintah ditolak oleh guardrail keamanan. Minta user menjalankan manual dengan /exec atau /do."})
            else:
                output, exit_code = await execute_command(cmd)
                await log_command(cmd, tier, None, output, exit_code)
                res_str = json.dumps({"command": cmd, "exit_code": exit_code, "output": output})
        except Exception as e:
            res_str = json.dumps({"error": str(e)})
    else:
        res_str = json.dumps({"error": f"Unknown tool: {func_name}"})
    
    return res_str, file_path

async def _generate_via_proxy(model_id: str, messages: list[dict], system_prompt: str = None) -> str:
    """Uses OpenAI compatible format via proxy URL."""
    from openai import AsyncOpenAI
    from config import NINER_ROUTER_KEY
    
    client = AsyncOpenAI(api_key=NINER_ROUTER_KEY, base_url=NINER_ROUTER_URL)
    
    formatted_messages = []
    if system_prompt:
        formatted_messages.append({"role": "system", "content": system_prompt})
    
    formatted_messages.extend(messages)
    
    response = await client.chat.completions.create(
        model=model_id,
        messages=formatted_messages
    )
    return response.choices[0].message.content

async def _generate_gemini(model_id: str, messages: list[dict], system_prompt: str = None) -> str:
    import google.generativeai as genai
    
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")
    
    genai.configure(api_key=GEMINI_API_KEY)
    
    generation_config = {}
    if system_prompt:
        # Note: Depending on generativeai version, system instruction is passed to the model initialization
        model = genai.GenerativeModel(model_name=model_id, system_instruction=system_prompt)
    else:
        model = genai.GenerativeModel(model_name=model_id)
        
    formatted_messages = []
    for msg in messages:
        # Gemini uses 'model' instead of 'assistant' for role
        role = "model" if msg["role"] == "assistant" else "user"
        formatted_messages.append({"role": role, "parts": [msg["content"]]})
        
    response = await model.generate_content_async(formatted_messages)
    return response.text

async def _generate_groq(model_id: str, messages: list[dict], system_prompt: str = None) -> str:
    from groq import AsyncGroq
    
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set")
        
    client = AsyncGroq(api_key=GROQ_API_KEY)
    
    formatted_messages = []
    if system_prompt:
        formatted_messages.append({"role": "system", "content": system_prompt})
    
    formatted_messages.extend(messages)
    
    response = await client.chat.completions.create(
        model=model_id,
        messages=formatted_messages
    )
    return response.choices[0].message.content

async def _generate_claude(model_id: str, messages: list[dict], system_prompt: str = None) -> str:
    from anthropic import AsyncAnthropic
    
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set")
        
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    
    kwargs = {
        "model": model_id,
        "max_tokens": 4096,
        "messages": messages
    }
    if system_prompt:
        kwargs["system"] = system_prompt
        
    response = await client.messages.create(**kwargs)
    
    # Claude response format
    if response.content and len(response.content) > 0:
        return response.content[0].text
    return ""
