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

# Retrieval is cross-lingual, and a Hindi question scores lower against an
# English passage than an English one would — keep this floor loose and let
# the persona refuse when nothing useful came back.
RETRIEVAL_TOP_K = 3
RETRIEVAL_MIN_SCORE = 0.70

PERSONA = """You are a voice assistant answering questions about {subject}.

You speak English and Hindi fluently. Always reply in the language the caller
used, whatever language the reference material happens to be written in.

For questions about {subject}, use only the information provided in the
conversation. If it is not there, say you don't have that detail.

For questions about yourself — what languages you speak, repeating something,
greetings — answer naturally.

Your first sentence must contain the answer. Never open with "Sure" or a
restatement of the question. Two sentences maximum.

Everything you say is spoken aloud, so write it the way it is said: no bullets,
symbols, markdown, or currency signs. Write prices, counts and dates as words —
six hundred fifty rupees, not 650. Leave phone numbers and pincodes as digits;
they are read out separately."""