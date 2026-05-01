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
    ExolveWebhookPayload,
    ExolveEvent,
    RespondRequest,
    RespondResponse,
    cmd_play,
    cmd_record,
    cmd_hangup,
    exolve_response,
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
# /call/webhook — МТС Exolve call lifecycle events
#
# Exolve sends events and expects a JSON response with next "Commands".
# All call control happens via this single endpoint.
# ---------------------------------------------------------------------------

@app.post("/call/webhook")
async def call_webhook(payload: ExolveWebhookPayload):
    call_id = payload.CallSessionID
    event = payload.EventType
    settings = get_settings()
    logger.info("Exolve event=%s call_id=%s", event, call_id)

    # --- Call started: play greeting then start listening ---
    if event == ExolveEvent.CALL_STARTED:
        _sessions[call_id] = {"started_at": time.time(), "turns": 0}
        try:
            greeting_bytes, _ = await text_to_speech(GREETING)
            greeting_url = _save_audio(call_id, "greeting", greeting_bytes)
            return exolve_response(
                cmd_play(greeting_url),
                cmd_record(
                    max_seconds=settings.max_record_seconds,
                    silence_timeout=settings.silence_timeout_seconds,
                ),
            )
        except Exception as exc:
            logger.error("Greeting failed call_id=%s: %s", call_id, exc)
            # Fall back to Exolve built-in TTS so the call doesn't hang
            from .telephony import cmd_say
            return exolve_response(
                cmd_say(GREETING),
                cmd_record(
                    max_seconds=settings.max_record_seconds,
                    silence_timeout=settings.silence_timeout_seconds,
                ),
            )

    # --- Recording ready: STT → LLM → TTS → play → record again ---
    if event == ExolveEvent.RECORD_FINISHED:
        record_url = payload.RecordURL
        if not record_url:
            logger.warning("OnRecordFinish without RecordURL call_id=%s", call_id)
            return exolve_response(
                cmd_record(
                    max_seconds=settings.max_record_seconds,
                    silence_timeout=settings.silence_timeout_seconds,
                )
            )

        session = _sessions.get(call_id, {})
        session["turns"] = session.get("turns", 0) + 1
        metrics = CallMetrics(call_id=call_id)

        try:
            # Download recording from Exolve storage
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(record_url)
            audio_bytes = r.content

            # STT
            recognized_text, stt_ms = await speech_to_text(audio_bytes, "oggopus")
            metrics.recognized_text = recognized_text
            metrics.latency_stt_ms = stt_ms
            logger.info("STT call_id=%s text=%r ms=%d", call_id, recognized_text, stt_ms)

            if not recognized_text.strip():
                # Empty input — listen again without saying anything
                return exolve_response(
                    cmd_record(
                        max_seconds=settings.max_record_seconds,
                        silence_timeout=settings.silence_timeout_seconds,
                    )
                )

            # LLM
            answer_text, llm_ms = await generate_answer(recognized_text)
            metrics.llm_answer = answer_text
            metrics.latency_llm_ms = llm_ms
            logger.info("LLM call_id=%s answer=%r ms=%d", call_id, answer_text, llm_ms)

            # TTS
            tts_bytes, tts_ms = await text_to_speech(answer_text)
            metrics.latency_tts_ms = tts_ms
            answer_url = _save_audio(call_id, f"turn{session['turns']}", tts_bytes)

            return exolve_response(
                cmd_play(answer_url),
                cmd_record(
                    max_seconds=settings.max_record_seconds,
                    silence_timeout=settings.silence_timeout_seconds,
                ),
            )

        except Exception as exc:
            metrics.error = str(exc)
            logger.exception("Record processing failed call_id=%s", call_id)
            from .telephony import cmd_say
            return exolve_response(
                cmd_say("Извини, не расслышал. Повтори, пожалуйста."),
                cmd_record(
                    max_seconds=settings.max_record_seconds,
                    silence_timeout=settings.silence_timeout_seconds,
                ),
            )
        finally:
            metrics.log()

    # --- Call finished ---
    if event == ExolveEvent.CALL_FINISHED:
        _sessions.pop(call_id, None)
        logger.info("Call finished call_id=%s", call_id)
        return exolve_response()

    # Unknown event — ack and do nothing
    return exolve_response()


# ---------------------------------------------------------------------------
# /call/audio — manual audio test endpoint (not used by Exolve in prod)
# Useful for curl/Postman testing of STT→LLM→TTS pipeline.
# ---------------------------------------------------------------------------

@app.post("/call/audio")
async def call_audio(
    call_id: str = Form(...),
    audio_format: str = Form("oggopus"),
    audio_url: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
):
    metrics = CallMetrics(call_id=call_id)
    try:
        if audio_file is not None:
            audio_bytes = await audio_file.read()
        elif audio_url:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(audio_url)
            audio_bytes = r.content
        else:
            raise HTTPException(status_code=400, detail="Provide audio_file or audio_url")

        recognized_text, stt_ms = await speech_to_text(audio_bytes, audio_format)
        metrics.recognized_text = recognized_text
        metrics.latency_stt_ms = stt_ms

        if not recognized_text.strip():
            return JSONResponse({"call_id": call_id, "recognized_text": "", "audio_url": None})

        answer_text, llm_ms = await generate_answer(recognized_text)
        metrics.llm_answer = answer_text
        metrics.latency_llm_ms = llm_ms

        tts_bytes, tts_ms = await text_to_speech(answer_text)
        metrics.latency_tts_ms = tts_ms

        out_url = _save_audio(call_id, "response", tts_bytes)
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
# /call/respond — pre-recognized text → TTS answer (testing / integrations)
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
# /audio/{filename} — serve generated TTS files (dev only)
# In prod: upload to Yandex Object Storage instead.
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
    is a durable public https:// link that Exolve can download.
    """
    filename = f"{call_id}_{tag}_{int(time.time())}.ogg"
    (_audio_dir() / filename).write_bytes(audio_bytes)
    base_url = get_settings().public_base_url
    return f"{base_url}/audio/{filename}"
