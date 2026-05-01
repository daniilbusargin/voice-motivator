"""Voximplant webhook event models and helper utilities.

Voximplant VoxEngine sends HTTP POST requests to our backend.
The call flow is driven by the VoxEngine JS scenario (see voximplant_scenario.js).

Incoming events we handle:
  - call_started   : new inbound/outbound call connected
  - audio_ready    : a recorded audio chunk URL is available
  - call_ended     : call terminated

Response format expected by VoxEngine:
  JSON with field 'audio_url' pointing to the TTS audio file we want played.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class VoxEvent(str, Enum):
    CALL_STARTED = "call_started"
    AUDIO_READY = "audio_ready"
    CALL_ENDED = "call_ended"


class VoximplantWebhookPayload(BaseModel):
    event: VoxEvent
    call_id: str
    audio_url: Optional[str] = None   # present on audio_ready
    caller: Optional[str] = None
    callee: Optional[str] = None


class VoximplantAudioPayload(BaseModel):
    call_id: str
    audio_url: Optional[str] = None   # URL where VX stored the recording
    audio_format: Optional[str] = "oggopus"


class RespondRequest(BaseModel):
    call_id: str
    text: str                          # pre-recognized text, skip STT


class RespondResponse(BaseModel):
    call_id: str
    answer_text: str
    audio_url: str                     # URL of the TTS audio to play
