"""Voximplant telephony integration.

Call flow (VoxEngine JS scenario → backend webhooks):
  1. Incoming call → VoxEngine answers, POST /call/webhook {event: "call_started"}
     Backend responds with {audio_url: <greeting>}
     VoxEngine plays greeting, then records caller.

  2. Recording done → VoxEngine POST /call/audio {call_id, audio_url, audio_format}
     Backend: STT → LLM → TTS → saves audio
     Responds with {audio_url: <answer>, recognized_text, answer_text}
     VoxEngine plays answer, records again.

  3. Call ends → VoxEngine POST /call/webhook {event: "call_ended"}

VoxEngine JS scenario: voximplant_scenario.js (upload to Voximplant dashboard).
Official docs: https://voximplant.com/docs/
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class VoxEvent(str, Enum):
    CALL_STARTED = "call_started"
    CALL_ENDED = "call_ended"


class VoximplantWebhookPayload(BaseModel):
    event: str
    call_id: str
    caller: Optional[str] = None
    callee: Optional[str] = None

    model_config = {"extra": "allow"}


class RespondRequest(BaseModel):
    call_id: str
    text: str


class RespondResponse(BaseModel):
    call_id: str
    answer_text: str
    audio_url: str
