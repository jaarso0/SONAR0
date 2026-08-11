import worker.patches  # noqa: F401  — must precede livekit plugin imports
import logging
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import openai, sarvam

from worker import config
import uuid
from livekit.agents import MetricsCollectedEvent
from worker.metrics import TurnRecorder


logger = logging.getLogger("sonar")



async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(...)
    recorder = TurnRecorder(session_id=uuid.uuid4().hex[:8])

    @session.on("metrics_collected")
    def on_metrics(ev: MetricsCollectedEvent):
        recorder.collect(ev.metrics)

    await session.start(room=ctx.room, agent=Agent(instructions=config.PERSONA))


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


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(
        stt=build_stt(),
        llm=build_llm(),
        tts=build_tts(),
        turn_detection="stt",
        min_endpointing_delay=0.07,
    )

    await session.start(
        room=ctx.room,
        agent=Agent(instructions=config.PERSONA),
    )

    await session.generate_reply(
        instructions="Greet the user in one short sentence and ask what they need."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="sonar"))