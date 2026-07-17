import httpx
from config import TAVILY_API_KEY
from utils.logger import logger

async def web_search(query: str, max_results: int = 5) -> dict:
    """
    Panggil Tavily API langsung (bukan lewat 9Router).
    Return dict hasil search, atau dict berisi 'error' kalau gagal.
    Timeout 10 detik.
    """
    if not TAVILY_API_KEY:
        return {"error": "TAVILY_API_KEY is not configured.", "results": []}

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return {"error": str(e), "results": []}
