import time
import httpx
from .config import get_settings
from .prompts import SYSTEM_PROMPT, SAFETY_TRIGGERS, SAFETY_RESPONSE
from .logger import logger

YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def _contains_safety_trigger(text: str) -> bool:
    lower = text.lower()
    return any(trigger in lower for trigger in SAFETY_TRIGGERS)


async def generate_answer(user_text: str) -> tuple[str, int]:
    """Return (answer_text, latency_ms)."""
    if _contains_safety_trigger(user_text):
        return SAFETY_RESPONSE, 0

    settings = get_settings()
    payload = {
        "modelUri": settings.gpt_model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": 0.4,
            "maxTokens": 100,
        },
        "messages": [
            {"role": "system", "text": SYSTEM_PROMPT},
            {"role": "user", "text": user_text},
        ],
    }

    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            YANDEX_GPT_URL,
            json=payload,
            headers={
                **settings.yandex_auth_header,
                "x-folder-id": settings.yandex_folder_id,
            },
        )
    latency_ms = int((time.monotonic() - t0) * 1000)

    if resp.status_code != 200:
        logger.error("YandexGPT error %s: %s", resp.status_code, resp.text)
        raise RuntimeError(f"YandexGPT returned {resp.status_code}: {resp.text}")

    data = resp.json()
    answer = data["result"]["alternatives"][0]["message"]["text"].strip()
    return answer, latency_ms
