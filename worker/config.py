import os
from dotenv import load_dotenv

load_dotenv()

LIVEKIT_URL = os.environ["LIVEKIT_URL"]
SARVAM_API_KEY = os.environ["SARVAM_API_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"

STT_MODEL = "saarika:v2.5"
TTS_MODEL = "bulbul:v2"
TTS_SPEAKER = "anushka"
LANGUAGE = "en-IN"

MAX_TURN_TOKENS = 120

PERSONA = """You are Sonar, a voice assistant answering questions on a phone call.

Your first sentence must contain the answer. Never open with "Sure",
"I'd be happy to", "Great question", or a restatement of the question.
Two sentences maximum unless explicitly asked for more.
Write numbers as words. Never use bullets, symbols, or markdown —
everything you write is spoken aloud.
If you don't know something, say so in one short sentence."""