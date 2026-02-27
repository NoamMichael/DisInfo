"""Yutori web agent API client.

Yutori provides Navigator (web agents) and Scouts (monitoring agents).
API details may be provided at hackathon. Using best-guess REST interface.
If this doesn't work, Tavily is the fallback for web verification.
"""

import httpx
from app.config import YUTORI_API_KEY

BASE_URL = "https://api.yutori.com/v1"


async def navigate(url: str, task: str) -> dict:
    """Send a Navigator agent to a URL to complete a task."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{BASE_URL}/navigate",
            json={"url": url, "task": task},
            headers={"Authorization": f"Bearer {YUTORI_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()


async def create_scout(query: str, sources: list[str] | None = None) -> dict:
    """Create a Scout to monitor web sources for a topic."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/scouts",
            json={"query": query, "sources": sources or []},
            headers={"Authorization": f"Bearer {YUTORI_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()


async def verify_claim(claim_text: str) -> dict:
    """Use Navigator to check a claim against fact-checking sites."""
    sites = [
        "https://www.politifact.com",
        "https://www.snopes.com",
        "https://www.reuters.com/fact-check",
    ]
    results = []
    for site in sites:
        try:
            result = await navigate(
                site,
                f"Search for information about this claim: '{claim_text}'. "
                "Report whether the claim has been fact-checked and what the verdict was.",
            )
            results.append({"source": site, "result": result})
        except Exception as e:
            results.append({"source": site, "error": str(e)})
    return {"claim": claim_text, "verifications": results}


async def smoke_test() -> str:
    try:
        result = await navigate("https://example.com", "What is on this page?")
        return f"OK: Yutori responded: {str(result)[:80]}"
    except Exception as e:
        return f"FAIL: Yutori - {e}"
