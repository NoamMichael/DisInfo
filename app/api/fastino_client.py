"""Fastino (Pioneer) personalization / memory API client.

Docs: https://fastino.ai/docs/overview
Auth: x-api-key in Authorization header
Endpoints: /personalization/ingest, /personalization/profile/query
"""

import httpx
from app.config import FASTINO_API_KEY

BASE_URL = "https://api.fastino.ai"
HEADERS = {
    "Authorization": f"x-api-key {FASTINO_API_KEY}",
    "Content-Type": "application/json",
}


async def _request(method: str, path: str, json_data: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            method,
            f"{BASE_URL}{path}",
            json=json_data,
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def ingest(user_id: str, documents: list[dict]) -> dict:
    """Store campaign fingerprint / memory entries.

    documents: list of {"doc_id": str, "kind": str, "title": str, "content": str}
    """
    return await _request("POST", "/personalization/ingest", {
        "user_id": user_id,
        "source": "disinfo_detector",
        "documents": documents,
    })


async def query_profile(user_id: str, question: str) -> dict:
    """Ask a natural-language question about stored user context."""
    return await _request("POST", "/personalization/profile/query", {
        "user_id": user_id,
        "question": question,
    })


async def store_campaign(campaign_id: str, fingerprint: str, metadata: dict | None = None) -> dict:
    """Convenience: store a disinfo campaign fingerprint."""
    return await ingest("disinfo_detector", [{
        "doc_id": campaign_id,
        "kind": "campaign_fingerprint",
        "title": f"Campaign {campaign_id}",
        "content": fingerprint,
    }])


async def recall_campaign(query: str) -> dict:
    """Convenience: check if a similar campaign was seen before."""
    return await query_profile("disinfo_detector", query)


async def smoke_test() -> str:
    try:
        result = await ingest("smoke_test_user", [{
            "doc_id": "test_001",
            "kind": "test",
            "title": "Smoke Test",
            "content": "This is a smoke test for Fastino API integration.",
        }])
        return f"OK: Fastino responded: {str(result)[:100]}"
    except Exception as e:
        return f"FAIL: Fastino - {e}"
