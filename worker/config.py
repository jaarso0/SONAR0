import os
from dotenv import load_dotenv

load_dotenv()

LIVEKIT_URL = os.environ["LIVEKIT_URL"]
SARVAM_API_KEY = os.environ["SARVAM_API_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"

STT_MODEL = "saarika:v2.5"
TTS_MODEL = "bulbul:v3"
TTS_SPEAKER = "shubh"
LANGUAGE = "en-IN"



MAX_TURN_TOKENS = 120

PERSONA = """You are a voice assistant answering questions about {subject}.

You speak English and Hindi fluently. Always reply in the language the caller used.

For questions about {subject}, use only the information provided in the
conversation. If it is not there, say you don't have that detail.

For questions about yourself — what languages you speak, repeating something,
greetings — answer naturally.

Your first sentence must contain the answer. Never open with "Sure" or a
restatement of the question. Two sentences maximum. Everything you say is
spoken aloud: no bullets, symbols, or markdown."""