import json
import os
import time
from pathlib import Path

from livekit.agents import metrics as lk_metrics

LOG_PATH = Path(os.getenv("SONAR_LOG_PATH", "logs/turns.jsonl"))

SARVAM_TTS_INR_PER_CHAR = 30 / 10_000
SARVAM_STT_INR_PER_SEC = 30 / 3600


class TurnRecorder:
    """Buffers metric events by speech_id and writes one line per completed turn."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.turns: dict[str, dict] = {}
        self.turn_index = 0
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _bucket(self, speech_id: str) -> dict:
        if speech_id not in self.turns:
            self.turn_index += 1
            self.turns[speech_id] = {
                "session_id": self.session_id,
                "speech_id": speech_id,
                "turn": self.turn_index,
                "started_at": time.time(),
            }
        return self.turns[speech_id]

    def collect(self, metric) -> None:
        if isinstance(metric, lk_metrics.EOUMetrics):
            bucket = self._bucket(metric.speech_id)
            bucket["t_eou_ms"] = round(metric.end_of_utterance_delay * 1000)
            bucket["t_stt_final_ms"] = round(metric.transcription_delay * 1000)

        elif isinstance(metric, lk_metrics.LLMMetrics):
            bucket = self._bucket(metric.speech_id)
            bucket["t_llm_ttft_ms"] = round(metric.ttft * 1000)
            bucket["tokens_in"] = metric.prompt_tokens
            bucket["tokens_out"] = metric.completion_tokens
            bucket["llm_tps"] = round(metric.tokens_per_second, 1)

        elif isinstance(metric, lk_metrics.TTSMetrics):
            bucket = self._bucket(metric.speech_id)
            bucket["t_tts_ttfb_ms"] = round(metric.ttfb * 1000)
            bucket["tts_chars"] = metric.characters_count
            bucket["audio_seconds"] = round(metric.audio_duration, 2)
            self._flush(metric.speech_id)

        elif isinstance(metric, lk_metrics.STTMetrics):
            bucket = self._bucket(metric.speech_id or "stt")
            bucket["stt_audio_seconds"] = round(metric.audio_duration, 2)

    def _flush(self, speech_id: str) -> None:
        turn = self.turns.pop(speech_id, None)
        if not turn:
            return

        turn["t_total_ms"] = (
            turn.get("t_eou_ms", 0)
            + turn.get("t_llm_ttft_ms", 0)
            + turn.get("t_tts_ttfb_ms", 0)
        )
        turn["cost_inr"] = round(
            turn.get("tts_chars", 0) * SARVAM_TTS_INR_PER_CHAR
            + turn.get("stt_audio_seconds", 0) * SARVAM_STT_INR_PER_SEC,
            4,
        )
        turn.pop("started_at", None)

        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(turn, ensure_ascii=False) + "\n")

        print(
            f"[turn {turn['turn']}] total {turn['t_total_ms']}ms  "
            f"eou {turn.get('t_eou_ms')}  ttft {turn.get('t_llm_ttft_ms')}  "
            f"tts {turn.get('t_tts_ttfb_ms')}  ₹{turn['cost_inr']}"
        )