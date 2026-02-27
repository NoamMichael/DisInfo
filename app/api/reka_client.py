"""Reka Vision API client."""

import httpx
from app.config import REKA_API_KEY

BASE_URL = "https://api.reka.ai/v1"


async def analyze_image(image_url: str, prompt: str = "Analyze this image for signs of manipulation, AI generation, or misleading visual content. List any concerns.") -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/chat",
            json={
                "model": "reka-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": image_url},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
            headers={"X-Api-Key": REKA_API_KEY},
        )
        resp.raise_for_status()
        return resp.json()


async def analyze_video(video_url: str, prompt: str = "Analyze this video for signs of manipulation, deepfakes, misleading graphics, or AI-generated content. Describe what you see and flag concerns.") -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{BASE_URL}/chat",
            json={
                "model": "reka-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "video_url", "video_url": video_url},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
            headers={"X-Api-Key": REKA_API_KEY},
        )
        resp.raise_for_status()
        return resp.json()


async def chat(text: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/chat",
            json={
                "model": "reka-flash",
                "messages": [{"role": "user", "content": [{"type": "text", "text": text}]}],
            },
            headers={"X-Api-Key": REKA_API_KEY},
        )
        resp.raise_for_status()
        return resp.json()


async def smoke_test() -> str:
    try:
        result = await chat("Say 'hello' in one word.")
        content = result.get("responses", [{}])[0].get("message", {}).get("content", "no content")
        return f"OK: Reka responded: {content[:80]}"
    except Exception as e:
        return f"FAIL: Reka - {e}"
