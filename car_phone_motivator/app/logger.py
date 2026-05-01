import logging
import json
import time
from typing import Optional
from dataclasses import dataclass, asdict, field


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("voice_motivator")


@dataclass
class CallMetrics:
    call_id: str
    recognized_text: str = ""
    llm_answer: str = ""
    latency_stt_ms: int = 0
    latency_llm_ms: int = 0
    latency_tts_ms: int = 0
    total_latency_ms: int = 0
    error: Optional[str] = None
    _start_ts: float = field(default_factory=time.time, repr=False, compare=False)

    def log(self):
        self.total_latency_ms = int((time.time() - self._start_ts) * 1000)
        data = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        logger.info("CALL_METRICS %s", json.dumps(data, ensure_ascii=False))
