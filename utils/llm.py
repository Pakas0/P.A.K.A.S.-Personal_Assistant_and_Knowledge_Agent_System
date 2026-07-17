import os
import logging
from config import GEMINI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY, NINER_ROUTER_URL, MODELS

logger = logging.getLogger("discord_agent")

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
