"""Tavily web search API client."""

import httpx
from app.config import TAVILY_API_KEY

BASE_URL = "https://api.tavily.com"


async def search(query: str, topic: str = "news", max_results: int = 5) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/search",
            json={
                "query": query,
                "topic": topic,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": "basic",
            },
            headers={"Authorization": f"Bearer {TAVILY_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()


async def smoke_test() -> str:
    try:
        result = await search("Cedar Valley water contamination", max_results=3)
        n = len(result.get("results", []))
        return f"OK: Tavily returned {n} results"
    except Exception as e:
        return f"FAIL: Tavily - {e}"
