"""Fastino / Pioneer AI — GLiNER-2 entity extraction & text classification.

Base URL: https://api.pioneer.ai
Auth: x-api-key header
OpenAPI: https://api.pioneer.ai/openapi.json

Key endpoints:
  POST /gliner-2          — extract_entities, classify_text, extract_json
  POST /gliner-2/async    — async version for large batches (>1M tokens)
  GET  /gliner-2/jobs/{id} — poll async job status
"""

import httpx
from app.config import FASTINO_API_KEY

BASE_URL = "https://api.pioneer.ai"
HEADERS = {
    "x-api-key": FASTINO_API_KEY,
    "Content-Type": "application/json",
}


async def extract_entities(
    text: str | list[str],
    labels: list[str],
    threshold: float = 0.3,
) -> dict:
    """Extract named entities from text using GLiNER-2.

    Args:
        text: Single string or list of strings.
        labels: Entity types to extract, e.g. ["organization", "location", "person"].
        threshold: Confidence cutoff (0-1). Default 0.3.

    Returns:
        {"result": {"entities": {"label": [{"text": ..., "confidence": ...}]}}, "token_usage": int}
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/gliner-2",
            headers=HEADERS,
            json={
                "task": "extract_entities",
                "text": text,
                "schema": labels,
                "threshold": threshold,
                "include_confidence": True,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def classify_text(
    text: str | list[str],
    categories: list[str],
    threshold: float = 0.3,
) -> dict:
    """Classify text into categories using GLiNER-2.

    Args:
        text: Single string or list of strings.
        categories: Category labels, e.g. ["disinformation", "news", "opinion"].
        threshold: Confidence cutoff.

    Returns:
        {"result": {"category": {"label": str, "confidence": float}}, "token_usage": int}
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/gliner-2",
            headers=HEADERS,
            json={
                "task": "classify_text",
                "text": text,
                "schema": {"categories": categories},
                "threshold": threshold,
                "include_confidence": True,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def extract_entities_batch(texts: list[str], labels: list[str],
                                  threshold: float = 0.3) -> list[dict]:
    """Extract entities from multiple texts in parallel."""
    import asyncio
    tasks = [extract_entities(t, labels, threshold) for t in texts]
    return await asyncio.gather(*tasks, return_exceptions=True)


async def classify_batch(texts: list[str], categories: list[str],
                          threshold: float = 0.3) -> list[dict]:
    """Classify multiple texts in parallel."""
    import asyncio
    tasks = [classify_text(t, categories, threshold) for t in texts]
    return await asyncio.gather(*tasks, return_exceptions=True)


async def analyze_post(text: str) -> dict:
    """Full analysis of a single post: entity extraction + classification.

    Returns combined results for the disinfo detection pipeline.
    """
    import asyncio
    entity_labels = [
        "organization", "person", "location", "chemical",
        "health_condition", "government_agency", "media_outlet",
    ]
    categories = [
        "disinformation", "conspiracy_theory", "news_report",
        "personal_opinion", "satire", "legitimate_concern",
    ]

    entities_result, classify_result = await asyncio.gather(
        extract_entities(text, entity_labels),
        classify_text(text, categories),
    )

    return {
        "entities": entities_result.get("result", {}).get("entities", {}),
        "classification": classify_result.get("result", {}).get("category", {}),
        "token_usage": (
            entities_result.get("token_usage", 0)
            + classify_result.get("token_usage", 0)
        ),
    }


async def smoke_test() -> str:
    try:
        result = await extract_entities(
            "CDC confirms water contamination in Springfield hospitals.",
            ["organization", "location"],
        )
        entities = result.get("result", {}).get("entities", {})
        n_entities = sum(len(v) for v in entities.values())
        return f"OK: Pioneer/GLiNER responded — {n_entities} entities extracted"
    except Exception as e:
        return f"FAIL: Fastino/Pioneer - {e}"
