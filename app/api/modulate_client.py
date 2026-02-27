"""Modulate Voice Intelligence API client.

Modulate provides deepfake detection, transcription, emotion detection.
SDK is C/C++ native but hackathon may expose a REST API.
Using best-guess REST interface.
"""

import httpx
from app.config import MODULATE_API_KEY

BASE_URL = "https://api.modulate.ai/v1"


async def detect_deepfake(audio_url: str) -> dict:
    """Detect if audio contains synthetic/AI-generated voice."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/deepfake/detect",
            json={"audio_url": audio_url},
            headers={"Authorization": f"Bearer {MODULATE_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()


async def transcribe(audio_url: str) -> dict:
    """Transcribe audio to text."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/transcribe",
            json={"audio_url": audio_url},
            headers={"Authorization": f"Bearer {MODULATE_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()


async def detect_emotion(audio_url: str) -> dict:
    """Analyze emotional signals in audio."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/emotion/detect",
            json={"audio_url": audio_url},
            headers={"Authorization": f"Bearer {MODULATE_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()


async def smoke_test() -> str:
    """Test with a small audio sample."""
    try:
        result = await detect_deepfake("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")
        return f"OK: Modulate responded: {str(result)[:80]}"
    except Exception as e:
        return f"FAIL: Modulate - {e}"
