import os
import uuid
import time
import httpx
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from typing import Optional

from .config import get_settings
from .llm_yandex import generate_answer
from .speech_yandex import speech_to_text, text_to_speech
from .telephony import (
    VoximplantWebhookPayload,
    VoxEvent,
    RespondRequest,
    RespondResponse,
)
from .logger import logger, CallMetrics
from .prompts import GREETING

app = FastAPI(title="Car Phone Motivator", version="0.1.0")

# In-memory session store — replace with Redis for multi-instance prod
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
# /chat — LLM smoke-test without a real call
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
#
# VoxEngine JS scenario sends call_started / call_ended events here.
# On call_started: we return greeting audio_url for VoxEngine to play.
# ---------------------------------------------------------------------------

@app.post("/call/webhook")
async def call_webhook(payload: VoximplantWebhookPayload):
    call_id = payload.call_id
    event = payload.event
    logger.info("Voximplant event=%s call_id=%s", event, call_id)

    if event == VoxEvent.CALL_STARTED:
        _sessions[call_id] = {"started_at": time.time(), "turns": 0}
        try:
            greeting_bytes, _ = await text_to_speech(GREETING)
            greeting_url = _save_audio(call_id, "greeting", greeting_bytes)
            return {"event": "greeting", "audio_url": greeting_url}
        except Exception as exc:
            logger.error("Greeting TTS failed call_id=%s: %s", call_id, exc)
            return {"event": "greeting", "audio_url": None}

    if event == VoxEvent.CALL_ENDED:
        _sessions.pop(call_id, None)
        return {"event": "ack"}

    return {"event": "ack"}


# ---------------------------------------------------------------------------
# /call/audio — receive recorded audio chunk from VoxEngine, run STT→LLM→TTS
#
# VoxEngine records caller's speech, sends the recording URL here.
# We return the answer audio_url for VoxEngine to play back.
# ---------------------------------------------------------------------------

@app.post("/call/audio")
async def call_audio(
    call_id: str = Form(...),
    audio_format: str = Form("oggopus"),
    audio_url: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
):
    metrics = CallMetrics(call_id=call_id)
    session = _sessions.get(call_id, {})
    session["turns"] = session.get("turns", 0) + 1

    try:
        # Fetch audio
        if audio_file is not None:
            audio_bytes = await audio_file.read()
        elif audio_url:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(audio_url)
            audio_bytes = r.content
        else:
            raise HTTPException(status_code=400, detail="Provide audio_file or audio_url")

        # STT
        recognized_text, stt_ms = await speech_to_text(audio_bytes, audio_format)
        metrics.recognized_text = recognized_text
        metrics.latency_stt_ms = stt_ms
        logger.info("STT call_id=%s text=%r ms=%d", call_id, recognized_text, stt_ms)

        if not recognized_text.strip():
            return JSONResponse({"call_id": call_id, "recognized_text": "", "audio_url": None})

        # LLM
        answer_text, llm_ms = await generate_answer(recognized_text)
        metrics.llm_answer = answer_text
        metrics.latency_llm_ms = llm_ms
        logger.info("LLM call_id=%s answer=%r ms=%d", call_id, answer_text, llm_ms)

        # TTS
        tts_bytes, tts_ms = await text_to_speech(answer_text)
        metrics.latency_tts_ms = tts_ms
        out_url = _save_audio(call_id, f"turn{session['turns']}", tts_bytes)

        return JSONResponse({
            "call_id": call_id,
            "recognized_text": recognized_text,
            "answer_text": answer_text,
            "audio_url": out_url,
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
# /call/respond — pre-recognized text → answer audio (testing / integrations)
# ---------------------------------------------------------------------------

@app.post("/call/respond")
async def call_respond(req: RespondRequest):
    metrics = CallMetrics(call_id=req.call_id, recognized_text=req.text)
    try:
        answer_text, llm_ms = await generate_answer(req.text)
        metrics.llm_answer = answer_text
        metrics.latency_llm_ms = llm_ms

        tts_bytes, tts_ms = await text_to_speech(answer_text)
        metrics.latency_tts_ms = tts_ms

        audio_url = _save_audio(req.call_id, "respond", tts_bytes)
        return RespondResponse(call_id=req.call_id, answer_text=answer_text, audio_url=audio_url)
    except Exception as exc:
        metrics.error = str(exc)
        logger.exception("call_respond error call_id=%s", req.call_id)
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        metrics.log()


# ---------------------------------------------------------------------------
# /audio/{filename} — serve TTS audio files (dev only)
# In prod: upload to Yandex Object Storage and return S3 URL instead.
# ---------------------------------------------------------------------------

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    path = _audio_dir() / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return Response(content=path.read_bytes(), media_type="audio/ogg")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_audio(call_id: str, tag: str, audio_bytes: bytes) -> str:
    """Write audio to disk and return a publicly accessible URL.

    In production, replace with upload to Yandex Object Storage so the URL
    is a durable public https:// link that Voximplant can download.
    """
    filename = f"{call_id}_{tag}_{int(time.time())}.ogg"
    (_audio_dir() / filename).write_bytes(audio_bytes)
    return f"{get_settings().public_base_url}/audio/{filename}"
