"""Reads ID-like digit runs out loud, on the way to TTS.

Sarvam speaks 282006 as a quantity — "two lakh eighty-two thousand six" — which
is right for a price and wrong for a pincode. Only identifiers are expanded
digit by digit; prices, counts and years are left alone, because reading those
as quantities is correct.

This runs on the answer rather than on the corpus: the model writes whatever it
writes, and the fix is deterministic instead of another thing to hope for.
"""

import re
from collections.abc import AsyncGenerator, AsyncIterable

HINDI_DIGITS = {"0": "शून्य", "1": "एक", "2": "दो", "3": "तीन", "4": "चार",
                "5": "पांच", "6": "छह", "7": "सात", "8": "आठ", "9": "नौ"}
ENGLISH_DIGITS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
                  "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}

IDENTIFIER = re.compile(
    r"\b0?\d{5}[\s-]?\d{5}\b"       # phone
    r"|\b\+?91[\s-]?\d{10}\b"       # phone with country code
    r"|\b\d{6}\b"                   # pincode
)

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# A digit run touching the end of the buffer may still be growing, so hold it
# back until the next chunk proves otherwise.
UNFINISHED = re.compile(r"[\d+][\d\s-]*$")


def expand_identifiers(text: str, hindi: bool) -> str:
    table = HINDI_DIGITS if hindi else ENGLISH_DIGITS

    def spell(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group())
        if 1900 <= int(digits) <= 2100:          # a year, not an identifier
            return match.group()
        return " ".join(table[d] for d in digits)

    return IDENTIFIER.sub(spell, text)


async def expand_stream(text: AsyncIterable[str], hindi: bool = False) -> AsyncGenerator[str, None]:
    """Expands across chunk boundaries — a phone number can arrive in pieces.

    Only the trailing digit run is buffered, so text flows to TTS with no
    added latency for ordinary prose.
    """
    buffer = ""

    async for chunk in text:
        buffer += chunk
        hindi = hindi or bool(DEVANAGARI.search(buffer))

        match = UNFINISHED.search(buffer)
        cut = match.start() if match else len(buffer)
        if cut:
            yield expand_identifiers(buffer[:cut], hindi)
        buffer = buffer[cut:]

    if buffer:
        yield expand_identifiers(buffer, hindi)
