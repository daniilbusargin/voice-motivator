import os
import uuid
import time
import base64
import httpx
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from typing import Optional

from .config import get_settings
from .llm_yandex import generate_answer
from .speech_yandex import speech_to_text, text_to_speech
from .telephony import (
    VoximplantWebhookPayload,
    VoximplantAudioPayload,
    RespondRequest,
    RespondResponse,
    VoxEvent,
)
from .logger import logger, CallMetrics
from .prompts import GREETING

app = FastAPI(title="Car Phone Motivator", version="0.1.0")

# In-memory session store (call_id -> last context), replace with Redis for prod
_sessions: dict[str, dict] = {}


def _audio_dir() -> Path:
    p = Path(get_settings().audio_store_path)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "car_phone_motivator"}


# ---------------------------------------------------------------------------
# /chat — quick LLM smoke-test, no audio
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    text: str
    call_id: Optional[str] = None


class ChatResponse(BaseModel):
    call_id: str
    answer: str
    latency_llm_ms: int


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    call_id = req.call_id or str(uuid.uuid4())
    metrics = CallMetrics(call_id=call_id, recognized_text=req.text)
    try:
        answer, latency = await generate_answer(req.text)
        metrics.llm_answer = answer
        metrics.latency_llm_ms = latency
        return ChatResponse(call_id=call_id, answer=answer, latency_llm_ms=latency)
    except Exception as exc:
        metrics.error = str(exc)
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        metrics.log()


# ---------------------------------------------------------------------------
# /call/webhook — Voximplant call lifecycle events
# ---------------------------------------------------------------------------

@app.post("/call/webhook")
async def call_webhook(payload: VoximplantWebhookPayload):
    call_id = payload.call_id
    logger.info("Webhook event=%s call_id=%s", payload.event, call_id)

    if payload.event == VoxEvent.CALL_STARTED:
        _sessions[call_id] = {"started_at": time.time()}
        # Return greeting TTS so VoxEngine plays it immediately
        try:
            audio_bytes, _ = await text_to_speech(GREETING)
            audio_url = _save_audio(call_id, "greeting", audio_bytes)
            return {"event": "greeting", "audio_url": audio_url}
        except Exception as exc:
            logger.error("Greeting TTS failed: %s", exc)
            return {"event": "greeting", "audio_url": None}

    if payload.event == VoxEvent.CALL_ENDED:
        _sessions.pop(call_id, None)
        return {"event": "ack"}

    # audio_ready is handled via /call/audio
    return {"event": "ack"}


# ---------------------------------------------------------------------------
# /call/audio — receive audio chunk from Voximplant, run STT+LLM+TTS
# ---------------------------------------------------------------------------

@app.post("/call/audio")
async def call_audio(
    call_id: str = Form(...),
    audio_format: str = Form("oggopus"),
    audio_url: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
):
    """Accept an audio chunk either as a file upload or a URL to download."""
    metrics = CallMetrics(call_id=call_id)

    try:
        # --- Fetch audio bytes ---
        if audio_file is not None:
            audio_bytes = await audio_file.read()
        elif audio_url:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(audio_url)
            audio_bytes = r.content
        else:
            raise HTTPException(status_code=400, detail="Provide audio_file or audio_url")

        # --- STT ---
        t0 = time.monotonic()
        recognized_text, stt_latency = await speech_to_text(audio_bytes, audio_format)
        metrics.recognized_text = recognized_text
        metrics.latency_stt_ms = stt_latency
        logger.info("STT call_id=%s text=%r latency_ms=%d", call_id, recognized_text, stt_latency)

        if not recognized_text.strip():
            return JSONResponse({"call_id": call_id, "recognized_text": "", "audio_url": None})

        # --- LLM ---
        answer_text, llm_latency = await generate_answer(recognized_text)
        metrics.llm_answer = answer_text
        metrics.latency_llm_ms = llm_latency
        logger.info("LLM call_id=%s answer=%r latency_ms=%d", call_id, answer_text, llm_latency)

        # --- TTS ---
        tts_bytes, tts_latency = await text_to_speech(answer_text)
        metrics.latency_tts_ms = tts_latency

        audio_url_out = _save_audio(call_id, "response", tts_bytes)
        return JSONResponse({
            "call_id": call_id,
            "recognized_text": recognized_text,
            "answer_text": answer_text,
            "audio_url": audio_url_out,
        })

    except HTTPException:
        raise
    except Exception as exc:
        metrics.error = str(exc)
        logger.exception("call_audio error call_id=%s", call_id)
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        metrics.log()


# ---------------------------------------------------------------------------
# /call/respond — when caller's text is already recognized externally
# ---------------------------------------------------------------------------

@app.post("/call/respond")
async def call_respond(req: RespondRequest):
    metrics = CallMetrics(call_id=req.call_id, recognized_text=req.text)
    try:
        answer_text, llm_latency = await generate_answer(req.text)
        metrics.llm_answer = answer_text
        metrics.latency_llm_ms = llm_latency

        tts_bytes, tts_latency = await text_to_speech(answer_text)
        metrics.latency_tts_ms = tts_latency

        audio_url = _save_audio(req.call_id, "respond", tts_bytes)
        return RespondResponse(
            call_id=req.call_id,
            answer_text=answer_text,
            audio_url=audio_url,
        )
    except Exception as exc:
        metrics.error = str(exc)
        logger.exception("call_respond error call_id=%s", req.call_id)
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        metrics.log()


# ---------------------------------------------------------------------------
# Serve stored audio files (for local/dev; in prod use object storage URL)
# ---------------------------------------------------------------------------

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    path = _audio_dir() / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return Response(content=path.read_bytes(), media_type="audio/ogg")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _save_audio(call_id: str, tag: str, audio_bytes: bytes) -> str:
    """Save audio to disk and return a URL path (relative, suitable for local dev).

    In production replace with upload to Yandex Object Storage and return
    the public https:// URL.
    """
    filename = f"{call_id}_{tag}_{int(time.time())}.ogg"
    path = _audio_dir() / filename
    path.write_bytes(audio_bytes)
    # Return relative path; caller should prepend public BASE_URL
    settings = get_settings()
    base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")
    return f"{base_url}/audio/{filename}"
