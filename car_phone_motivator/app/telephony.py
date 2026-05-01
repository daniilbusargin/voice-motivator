"""МТС Exolve telephony integration.

Call flow (webhook command-response pattern):
  1. Exolve → POST /call/webhook  {EventType: "OnCallStart", ...}
     Backend ← responds with PlayAudio(greeting) + StartRecord commands
  2. Caller speaks; Exolve records audio.
  3. Exolve → POST /call/webhook  {EventType: "OnRecordFinish", RecordURL: "..."}
     Backend: downloads recording → STT → LLM → TTS → saves audio
     Backend ← responds with PlayAudio(answer) + StartRecord commands
  4. Repeat from step 2 until call ends.
  5. Exolve → POST /call/webhook  {EventType: "OnCallFinish"}
     Backend ← responds {"Commands": []}

Official docs: https://exolve.ru/docs/
All field names below match Exolve VoiceBot API v1.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Exolve → Backend: incoming webhook payload
# ---------------------------------------------------------------------------

class ExolveEvent(str, Enum):
    CALL_STARTED = "OnCallStart"
    RECORD_FINISHED = "OnRecordFinish"
    PLAY_FINISHED = "OnPlayFinish"
    CALL_FINISHED = "OnCallFinish"


class ExolveWebhookPayload(BaseModel):
    """Subset of fields Exolve sends on every webhook event."""
    CallSessionID: str
    EventType: str
    ApplicationID: Optional[str] = None
    CallerID: Optional[str] = None    # caller phone number
    CalleeID: Optional[str] = None    # dialled number
    RecordURL: Optional[str] = None   # present on OnRecordFinish

    model_config = {"extra": "allow"}  # tolerate unknown fields


# ---------------------------------------------------------------------------
# Backend → Exolve: response commands
# ---------------------------------------------------------------------------

def cmd_play(audio_url: str) -> dict:
    return {"Command": "PlayAudio", "AudioURL": audio_url}


def cmd_record(max_seconds: int = 10, silence_timeout: int = 2) -> dict:
    return {
        "Command": "StartRecord",
        "MaxDuration": max_seconds,
        "SilenceTimeout": silence_timeout,
    }


def cmd_say(text: str, voice: str = "male") -> dict:
    """Use Exolve's built-in TTS (fallback when SpeechKit is unavailable)."""
    return {"Command": "SayText", "Text": text, "Voice": voice}


def cmd_hangup() -> dict:
    return {"Command": "EndCall"}


def exolve_response(*commands: dict) -> dict:
    """Wrap commands list into the Exolve response envelope."""
    return {"Commands": list(commands)}


# ---------------------------------------------------------------------------
# /call/respond models (provider-agnostic, used by internal endpoint)
# ---------------------------------------------------------------------------

class RespondRequest(BaseModel):
    call_id: str
    text: str


class RespondResponse(BaseModel):
    call_id: str
    answer_text: str
    audio_url: str
