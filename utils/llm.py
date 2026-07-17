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
                        "rows": {"type": "array"}
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

async def call_llm_with_tools(model_alias: str, messages: list[dict], thread_id: str, system_prompt: str = None, max_iterations: int = 3, message_obj = None) -> tuple[str, list[str]]:
    """
    Wrapper around generate_response to handle tool calling loop.
    message_obj is the Discord message to edit with progress indicator.
    Returns (response_text, list_of_file_paths)
    """
    iteration = 0
    current_messages = messages.copy()
    generated_files = []
    
    # Send thinking indicator
    indicator_msg = None
    if message_obj:
        indicator_msg = await message_obj.reply("🤔 Thinking...")
        
    while iteration < max_iterations:
        iteration += 1
        
        # We need to use proxy specifically to pass tools, or implement tool usage for all SDKs.
        # For simplicity in this batch, we will use the OpenAI compatible proxy format logic.
        # If we have direct SDKs, we might need a custom tool handler. To keep it simple,
        # we will enforce proxy format (which supports tools natively via OpenAI schema) for tools.
        # But wait, generate_response handles proxy vs SDK internally. We will just use proxy if tools are needed,
        # or implement generic openai-compatible tool calls.
        
        model_id = MODELS[model_alias]
        
        from openai import AsyncOpenAI
        from config import NINER_ROUTER_KEY
        
        # Use proxy directly for tool calls to guarantee OpenAI schema compatibility
        client = AsyncOpenAI(api_key=NINER_ROUTER_KEY if NINER_ROUTER_KEY else "dummy", base_url=NINER_ROUTER_URL if NINER_ROUTER_URL else "https://api.groq.com/openai/v1")
        if not NINER_ROUTER_URL and model_alias == "groq":
             client = AsyncOpenAI(api_key=GROQ_API_KEY)
        
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
            
        for m in current_messages:
            fm = {}
            if m["role"] == "tool_call":
                fm["role"] = "assistant"
                fm["content"] = f"*[Memanggil alat {m.get('tool_name', 'unknown')}: {m.get('content', '')}]*"
            elif m["role"] == "tool_result":
                fm["role"] = "user"
                # Truncate content slightly if needed for history
                content = m.get("content", "")
                if len(content) > 1500:
                    content = content[:1500] + "...(truncated)"
                fm["content"] = f"*[Hasil alat {m.get('tool_name', 'unknown')}]:*\n{content}"
            else:
                fm["role"] = m["role"]
                fm["content"] = m["content"]
                
            formatted_messages.append(fm)
            
        try:
            response = await client.chat.completions.create(
                model=model_id,
                messages=formatted_messages,
                tools=[WEB_SEARCH_TOOL_SCHEMA, GENERATE_DOCUMENT_TOOL_SCHEMA, EXECUTE_COMMAND_TOOL_SCHEMA],
                tool_choice="auto"
            )
        except Exception as e:
            if indicator_msg:
                await indicator_msg.delete()
            fallback_text = await generate_response(model_alias, messages, system_prompt)
            return fallback_text, generated_files
            
        msg = response.choices[0].message
        
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                func_args = tool_call.function.arguments
                
                await save_tool_call(thread_id, func_name, func_args, model_alias)
                current_messages.append({
                    "role": "tool_call", 
                    "content": func_args, 
                    "tool_name": func_name
                })
                
                
                if func_name == "web_search":
                    if indicator_msg:
                        try:
                            args_dict = json.loads(func_args)
                            query = args_dict.get("query", "...")
                            await indicator_msg.edit(content=f"🔍 Searching: \"{query}\"...")
                        except:
                            await indicator_msg.edit(content="🔍 Searching...")
                            
                    # Execute tool
                    try:
                        args = json.loads(func_args)
                        query = args.get("query", "")
                        max_res = args.get("max_results", 5)
                        res = await web_search(query, max_res)
                        res_str = json.dumps(res)
                    except Exception as e:
                        res_str = json.dumps({"error": str(e)})
                        
                elif func_name == "generate_document":
                    if indicator_msg:
                        try:
                            args_dict = json.loads(func_args)
                            format_type = args_dict.get("format", "document")
                            title = args_dict.get("title", "...")
                            await indicator_msg.edit(content=f"📄 Membuat dokumen {format_type}: \"{title}\"...")
                        except:
                            await indicator_msg.edit(content="📄 Membuat dokumen...")
                            
                    try:
                        args = json.loads(func_args)
                        res = await generate_document(
                            args.get("format"),
                            args.get("title"),
                            args.get("sections"),
                            args.get("table_data")
                        )
                        res_str = json.dumps(res)
                        if "file_path" in res:
                            generated_files.append(res["file_path"])
                    except Exception as e:
                        res_str = json.dumps({"error": str(e)})
                        
                elif func_name == "execute_shell_command":
                    try:
                        args_dict = json.loads(func_args)
                        cmd = args_dict.get("command", "")
                        
                        if indicator_msg:
                            await indicator_msg.edit(content=f"💻 Mengeksekusi: `{cmd}`...")
                            
                        # Security Check
                        tier = classify_command(cmd)
                        if tier == TIER_APPROVAL:
                            res_str = json.dumps({
                                "error": "Tindakan ditolak oleh sistem keamanan (Guardrails). Perintah ini bersifat destruktif/berisiko tinggi dan membutuhkan otorisasi manual. Beritahu user untuk menjalankan perintah ini secara eksplisit menggunakan slash command /exec atau /do."
                            })
                        else:
                            # TIER_AUTO or TIER_NOTIFY
                            output, exit_code = await execute_command(cmd)
                            await log_command(cmd, tier, None, output, exit_code)
                            
                            res_dict = {
                                "command": cmd,
                                "exit_code": exit_code,
                                "output": output
                            }
                            res_str = json.dumps(res_dict)
                            
                    except Exception as e:
                        res_str = json.dumps({"error": str(e)})
                        
                else:
                    res_str = json.dumps({"error": f"Unknown tool: {func_name}"})
                        
                # Save result
                    # Truncate result if too long to save memory
                    if len(res_str) > 3000:
                        res_str = res_str[:3000] + "...(truncated)"
                        
                    await save_tool_result(thread_id, func_name, res_str, model_alias)
                    current_messages.append({
                        "role": "tool_result", 
                        "content": res_str, 
                        "tool_name": func_name
                    })
        else:
            if indicator_msg:
                await indicator_msg.delete()
            return msg.content, generated_files
            
    if indicator_msg:
        await indicator_msg.delete()
    return "⚠️ Terlalu banyak iterasi pencarian. Silakan persempit pertanyaan Anda.", generated_files

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
