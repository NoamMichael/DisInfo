"""Modulate Voice Intelligence API client.

Docs: https://modulate-developer-apis.com/web/docs.html
Base URL: https://modulate-developer-apis.com
Auth: X-API-Key header

Velma-2 endpoints:
  - /api/velma-2-stt-batch — multilingual batch transcription with diarization, emotion, accent, PII
  - /api/velma-2-stt-batch-english-vfast — fast English-only transcription (Opus only)
  - /api/velma-2-stt-streaming — WebSocket real-time transcription
"""

import httpx
from app.config import MODULATE_API_KEY

BASE_URL = "https://modulate-developer-apis.com"
HEADERS = {"X-API-Key": MODULATE_API_KEY}


async def transcribe_batch(
    audio_data: bytes,
    filename: str = "audio.mp3",
    speaker_diarization: bool = True,
    emotion_signal: bool = True,
) -> dict:
    """Batch transcription with diarization + emotion detection.

    Supports: AAC, AIFF, FLAC, MP3, MP4, MOV, OGG, Opus, WAV, WebM (up to 100MB).
    """
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{BASE_URL}/api/velma-2-stt-batch",
            headers=HEADERS,
            files={"upload_file": (filename, audio_data)},
            data={
                "speaker_diarization": str(speaker_diarization).lower(),
                "emotion_signal": str(emotion_signal).lower(),
            },
        )
        resp.raise_for_status()
        return resp.json()


async def transcribe_fast_english(audio_data: bytes, filename: str = "audio.opus") -> dict:
    """Fast English-only batch transcription. Opus audio only."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/api/velma-2-stt-batch-english-vfast",
            headers=HEADERS,
            files={"upload_file": (filename, audio_data)},
        )
        resp.raise_for_status()
        return resp.json()


async def transcribe_url(audio_url: str) -> dict:
    """Download audio from URL, then transcribe with full features."""
    async with httpx.AsyncClient(timeout=30) as client:
        dl = await client.get(audio_url)
        dl.raise_for_status()
        audio_data = dl.content

    ext = audio_url.rsplit(".", 1)[-1].split("?")[0] if "." in audio_url else "mp3"
    return await transcribe_batch(audio_data, filename=f"audio.{ext}")


async def smoke_test() -> str:
    """Test with a small synthesized audio tone (WAV)."""
    import struct
    import io

    # Generate a minimal 1-second WAV file (sine wave)
    sample_rate = 16000
    duration = 1
    n_samples = sample_rate * duration
    buf = io.BytesIO()
    # WAV header
    data_size = n_samples * 2
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    import math
    for i in range(n_samples):
        sample = int(16000 * math.sin(2 * math.pi * 440 * i / sample_rate))
        buf.write(struct.pack("<h", sample))

    wav_data = buf.getvalue()

    try:
        result = await transcribe_batch(wav_data, filename="test.wav")
        text = result.get("text", "")
        n_utterances = len(result.get("utterances", []))
        return f"OK: Modulate responded — text='{text[:60]}', {n_utterances} utterances"
    except Exception as e:
        return f"FAIL: Modulate - {e}"
