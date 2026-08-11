import asyncio
import hashlib
import json
import os
import sys
import re
from pathlib import Path

from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

MODEL = "llama-3.3-70b-versatile"
CONCURRENCY = 2
PROMPT_VERSION = "v3"

LANGUAGES = {
    "en-IN": ("Indian English", "Latin"),
    "hi-IN": ("Hindi", "Devanagari"),
}

PROMPT = """You turn reference text into what a person would actually say out loud on a phone call.

Section: {heading_path}
Business: {business}

Text:
{source}

Rules:
- Reply in {language_name} using {script} script. Nothing else.
- Expand every number, price, phone number, and date into words as they are spoken.
- No bullets, symbols, markdown, asterisks, or currency signs.
- Lead with the most useful fact. Three sentences maximum.
- If the text is only slogans, headings, or navigation with no real information, reply with exactly: SKIP
- Lead with the fact a caller is most likely to want: price, address, phone, or timing.
  Atmosphere and philosophy come last, or not at all.
  NUMBER RULES — follow exactly:
- Phone numbers, pincodes, plot numbers, and any ID: read EVERY digit
  separately. 282006 becomes दो आठ दो शून्य शून्य छह. Never group digits
  into tens, hundreds, thousands, or lakhs.
- Only prices and counts are spoken as quantities. 650 rupees becomes
  छह सौ पचास रुपये.
- Never state a fact that is not in the source text. No opening hours,
  no availability, no benefits unless written above.
- Any number already written out as words must be copied exactly as-is. Never
  recombine word-digits into tens, hundreds, thousands, or lakhs.
Return only the spoken text."""

HINDI_DIGITS = {"0": "शून्य", "1": "एक", "2": "दो", "3": "तीन", "4": "चार",
                "5": "पांच", "6": "छह", "7": "सात", "8": "आठ", "9": "नौ"}
ENGLISH_DIGITS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
                  "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}

PHONE_OR_PIN = re.compile(
    r"\b0?\d{5}[\s-]?\d{5}\b"      # phone
    r"|\b\d{6}\b"                   # pincode
    r"|(?<=[Pp]lot )\d{3,5}\b"      # plot number
)

def pre_expand_sequences(text: str, lang: str) -> str:
    """Expand phone numbers and pincodes digit-by-digit before the LLM sees them."""
    table = HINDI_DIGITS if lang == "hi-IN" else ENGLISH_DIGITS

    def expand(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group())
        if 1900 <= int(digits) <= 2100:          
            return match.group()
        return " ".join(table[d] for d in digits)

    return PHONE_OR_PIN.sub(expand, text)

def cache_key(source: str, lang: str) -> str:
    return hashlib.sha1(f"{PROMPT_VERSION}|{lang}|{source}".encode()).hexdigest()


from groq import AsyncGroq, RateLimitError

async def rewrite_one(client, chunk, lang, business, semaphore, cache):
    key = cache_key(chunk["source"], lang)
    if key in cache:
        return chunk["id"], lang, cache[key]

    language_name, script = LANGUAGES[lang]
    source_text = pre_expand_sequences(chunk["source"], lang)      

    async with semaphore:
        for attempt in range(5):
            try:
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "user", "content": PROMPT.format(
                        heading_path=chunk["heading_path"],
                        business=business,
                        source=source_text,                         
                        language_name=language_name,
                        script=script,
                    )}],
                    temperature=0.3,
                    max_tokens=250,
                )
                text = response.choices[0].message.content.strip()
                cache[key] = text
                return chunk["id"], lang, text

            except RateLimitError as error:
                wait = float(getattr(error.response.headers, "get", lambda k, d: d)("retry-after", 0)) or 10 * (attempt + 1)
                print(f"  rate limited, waiting {wait:.0f}s")
                await asyncio.sleep(wait)

            except Exception as error:
                if attempt == 4:
                    print(f"  FAILED {chunk['id']} {lang}: {error}")
                    return chunk["id"], lang, None
                await asyncio.sleep(2 ** attempt)

    return chunk["id"], lang, None

async def generate_spoken(pack_dir: Path, languages: list[str], business: str) -> int:
    chunks_path = pack_dir / "build" / "chunks.json"
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))

    cache_path = pack_dir / "build" / "spoken_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    by_id = {c["id"]: c for c in chunks}
    semaphore = asyncio.Semaphore(CONCURRENCY)
    client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

    tasks = [
        rewrite_one(client, chunk, lang, business, semaphore, cache)
        for chunk in chunks
        for lang in languages
        if lang not in chunk.get("spoken", {})
    ]
    print(f"  {len(tasks)} rewrites ({len(chunks)} chunks x {len(languages)} languages)")

    done = 0
    for coro in asyncio.as_completed(tasks):
        chunk_id, lang, text = await coro
        done += 1
        if done % 20 == 0:
            print(f"  {done}/{len(tasks)}")
        if text and text != "SKIP":
            by_id[chunk_id].setdefault("spoken", {})[lang] = text

    kept = [c for c in chunks if c.get("spoken")]
    chunks_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    print(f"  kept {len(kept)} of {len(chunks)} chunks ({len(chunks) - len(kept)} skipped)")
    return len(kept)


if __name__ == "__main__":
    pack_dir = Path("packs") / sys.argv[1]
    languages = sys.argv[2].split(",") if len(sys.argv) > 2 else ["en-IN"]
    business = json.loads((pack_dir / "meta.json").read_text()).get("source_url", "")
    asyncio.run(generate_spoken(pack_dir, languages, business))