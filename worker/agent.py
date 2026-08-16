import worker.patches  # noqa: F401  — must precede livekit plugin imports

import json
import logging
import os
import sys
import uuid
from pathlib import Path

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    MetricsCollectedEvent,
    WorkerOptions,
    cli,
)
from livekit.plugins import openai, sarvam

from worker import config
from worker.metrics import TurnRecorder
from worker.retrieval import FileRetriever
from worker.verbalize import expand_stream

logger = logging.getLogger("sonar")

# The per-turn cost line prints ₹, which the default Windows codepage cannot
# encode — without this the metrics handler raises whenever output is redirected.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Used only when a job arrives without metadata, i.e. `python -m worker.agent console`.
FALLBACK_PACK_ID = os.getenv("SONAR_PACK_ID", "")


def pack_id_for_job(ctx: JobContext) -> str:
    """The API dispatches with {"pack_id": ...}; a bare id is accepted too."""
    metadata = (ctx.job.metadata or "").strip()
    if not metadata:
        return FALLBACK_PACK_ID
    try:
        return json.loads(metadata).get("pack_id", "")
    except json.JSONDecodeError:
        return metadata


def build_llm() -> openai.LLM:
    return openai.LLM(
        model=config.GROQ_MODEL,
        api_key=config.GROQ_API_KEY,
        base_url=config.GROQ_BASE_URL,
        temperature=0.3,
    )


def build_stt() -> sarvam.STT:
    return sarvam.STT(
        language=config.LANGUAGE,
        model=config.STT_MODEL,
        api_key=config.SARVAM_API_KEY,
    )


def build_tts() -> sarvam.TTS:
    return sarvam.TTS(
        target_language_code=config.LANGUAGE,
        speaker=config.TTS_SPEAKER,
        model=config.TTS_MODEL,
        api_key=config.SARVAM_API_KEY,
    )


class SonarAgent(Agent):
    def __init__(self, retriever: FileRetriever, lang: str):
        super().__init__(instructions=config.PERSONA.format(subject=retriever.subject))
        self.retriever = retriever
        self.lang = lang

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        question = new_message.text_content
        if not question:
            return

        hits = self.retriever.search(question,
                                     k=config.RETRIEVAL_TOP_K,
                                     min_score=config.RETRIEVAL_MIN_SCORE)
        if not hits:
            logger.info("no context above %.2f for %r", config.RETRIEVAL_MIN_SCORE, question)
            return

        logger.info("retrieved %s", [round(h["score"], 3) for h in hits])

        context = "\n\n".join(f"{h['heading_path']}\n{h['text']}" for h in hits)
        turn_ctx.add_message(
            role="assistant",
            content=f"Reference material about {self.retriever.subject}:\n{context}",
        )

    async def tts_node(self, text, model_settings):
        """Spell out identifiers for the speech path only — the transcript the
        caller reads keeps the digits."""
        expanded = expand_stream(text, hindi=self.lang.startswith("hi"))
        return Agent.default.tts_node(self, expanded, model_settings)


async def entrypoint(ctx: JobContext):
    pack_id = pack_id_for_job(ctx)
    if not pack_id:
        raise RuntimeError(
            "no pack_id in the job metadata — dispatch from the API, "
            "or set SONAR_PACK_ID to run this from the console"
        )

    await ctx.connect()

    retriever = FileRetriever(Path("packs") / pack_id)
    recorder = TurnRecorder(session_id=uuid.uuid4().hex[:8])

    session = AgentSession(
        stt=build_stt(),
        llm=build_llm(),
        tts=build_tts(),
        turn_detection="stt",
        min_endpointing_delay=0.2,
        min_interruption_duration=0.7,
        min_interruption_words=2,
    )

    @session.on("metrics_collected")
    def on_metrics(ev: MetricsCollectedEvent):
        recorder.collect(ev.metrics)

    await session.start(room=ctx.room, agent=SonarAgent(retriever, config.LANGUAGE))

    await session.generate_reply(
        instructions="Greet the caller in one short sentence and ask how you can help."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="sonar"))