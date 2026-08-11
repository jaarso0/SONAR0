import worker.patches  # noqa: F401  — must precede livekit plugin imports

import logging
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

logger = logging.getLogger("sonar")

PACK_ID = "a7d7c3c1a58a"


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
        super().__init__(instructions=config.PERSONA)
        self.retriever = retriever
        self.lang = lang

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        question = new_message.text_content
        print(">>> HOOK FIRED", repr(question))
        if not question:
            return

        hits = self.retriever.search(question, self.lang, k=3)
        hits = [h for h in hits if h["score"] > 0.75]
        if not hits:
            print(">>> no relevant context")
            return
        print(f">>> RETRIEVED {[round(h['score'], 3) for h in hits]}")

        context = "\n".join(h["text"] for h in hits)
        turn_ctx.add_message(
            role="assistant",
            content=f"Relevant information from the business:\n{context}",
        )


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    retriever = FileRetriever(Path("packs") / PACK_ID, ["en-IN", "hi-IN"])
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

    await session.start(room=ctx.room, agent=SonarAgent(retriever, "en-IN"))

    await session.generate_reply(
        instructions="Greet the caller in one short sentence and ask how you can help."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="sonar"))