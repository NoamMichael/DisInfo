"""Yutori web agent API client.

Yutori provides Navigator (browsing), Research, and Scouts (monitoring).
Docs: https://docs.yutori.com/
Auth: X-API-KEY header
"""

import httpx
from app.config import YUTORI_API_KEY

BASE_URL = "https://api.yutori.com/v1"
HEADERS = {
    "X-API-KEY": YUTORI_API_KEY,
    "Content-Type": "application/json",
}


async def browse(task: str, start_url: str = "https://google.com") -> dict:
    """Create a browsing task — Navigator goes to a URL and completes a task."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{BASE_URL}/browsing/tasks",
            json={"task": task, "start_url": start_url},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def research(query: str) -> dict:
    """Deep web research using 100+ MCP tools."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{BASE_URL}/research/tasks",
            json={"query": query},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def create_scout(query: str) -> dict:
    """Create a Scout for continuous web monitoring."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/scouting/tasks",
            json={"query": query},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def verify_claim(claim_text: str) -> dict:
    """Use browsing to check a claim against fact-checking sites."""
    results = []
    sites = [
        ("https://www.politifact.com", "PolitiFact"),
        ("https://www.snopes.com", "Snopes"),
        ("https://www.reuters.com/fact-check", "Reuters"),
    ]
    for url, name in sites:
        try:
            result = await browse(
                task=f"Search for information about this claim: '{claim_text}'. "
                     "Report whether the claim has been fact-checked and what the verdict was.",
                start_url=url,
            )
            results.append({"source": name, "url": url, "result": result})
        except Exception as e:
            results.append({"source": name, "url": url, "error": str(e)})
    return {"claim": claim_text, "verifications": results}


async def smoke_test() -> str:
    try:
        result = await browse(
            task="What is on this page? Return the main heading.",
            start_url="https://example.com",
        )
        return f"OK: Yutori responded: {str(result)[:100]}"
    except Exception as e:
        return f"FAIL: Yutori - {e}"
