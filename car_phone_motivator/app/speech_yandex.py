import time
import httpx
from .config import get_settings
from .logger import logger

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"


async def speech_to_text(audio_bytes: bytes, audio_format: str = "oggopus") -> tuple[str, int]:
    """Return (recognized_text, latency_ms).

    audio_format: 'oggopus' | 'lpcm' | 'mp3'
    For lpcm also pass sampleRateHertz param (8000 for telephony).
    """
    settings = get_settings()
    params = {
        "lang": settings.speechkit_stt_lang,
        "format": audio_format,
        "folderId": settings.yandex_folder_id,
    }
    if audio_format == "lpcm":
        params["sampleRateHertz"] = "8000"

    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            STT_URL,
            content=audio_bytes,
            params=params,
            headers={
                **settings.auth_header,
                "Content-Type": "application/octet-stream",
            },
        )
    latency_ms = int((time.monotonic() - t0) * 1000)

    if resp.status_code != 200:
        logger.error("SpeechKit STT error %s: %s", resp.status_code, resp.text)
        raise RuntimeError(f"SpeechKit STT returned {resp.status_code}: {resp.text}")

    result = resp.json().get("result", "")
    return result, latency_ms


async def text_to_speech(text: str) -> tuple[bytes, int]:
    """Return (audio_bytes ogg/opus, latency_ms)."""
    settings = get_settings()
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            TTS_URL,
            data={
                "text": text,
                "lang": "ru-RU",
                "voice": settings.speechkit_tts_voice,
                "speed": settings.speechkit_tts_speed,
                "format": "oggopus",
                "folderId": settings.yandex_folder_id,
            },
            headers=settings.auth_header,
        )
    latency_ms = int((time.monotonic() - t0) * 1000)

    if resp.status_code != 200:
        logger.error("SpeechKit TTS error %s: %s", resp.status_code, resp.text)
        raise RuntimeError(f"SpeechKit TTS returned {resp.status_code}: {resp.text}")

    return resp.content, latency_ms
