
import re
from collections.abc import AsyncGenerator, AsyncIterable

HINDI_DIGITS = {"0": "शून्य", "1": "एक", "2": "दो", "3": "तीन", "4": "चार",
                "5": "पांच", "6": "छह", "7": "सात", "8": "आठ", "9": "नौ"}
ENGLISH_DIGITS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
     "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}

IDENTIFIER = re.compile(
    r"\b0?\d{5}[\s-]?\d{5}\b"       # phone
   r"|\b\+?91[\s-]?\d{10}\b"       # phone with code cntry
    r"|\b\d{6}\b"                   #for pincode
)

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
UNFINISHED = re.compile(r"[\d+][\d\s-]*$")

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty",
        6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}


YEARLIKE = re.compile(r"(?<!\d)(?<!\d[.,])(1[5-9]\d\d|20\d\d)(s)?(?!\w)(?![.,]\d)")
CUE_BEFORE = re.compile(
    r"(?:\b(?:in|since|by|from|until|till|before|after|during|around|about"
    r"|circa|between|and|to|of|year|years)\b\W{0,3}|\d{4}\s*[-–—]\s*)$",
    re.IGNORECASE,
)
CUE_AFTER = re.compile(r"^\s*(?:AD|BC|CE|BCE)\b|^\s*[-–—]\s*\d{4}\b")
MONEY_BEFORE = re.compile(r"(?:₹|Rs\.?|INR|\$)\s*$", re.IGNORECASE)


def _under_hundred(n: int) -> str:
    if n < 20:
        return ONES[n]
    tens, rest = divmod(n, 10)
    return TENS[tens] + (f"-{ONES[rest]}" if rest else "")


def say_year(year: int, plural: bool = False) -> str:
    """1947 -> nineteen forty-seven, 2025 -> twenty twenty-five, 1905 -> nineteen oh five."""
    century, rest = divmod(year, 100)
    if 2000 <= year <= 2009:                     
        said = "two thousand" + (f" {ONES[rest]}" if rest else "")
        return said + "s" if plural else said
    if rest == 0:
        return f"{_under_hundred(century)} hundred" + ("s" if plural else "")
    if plural:                                   
        return f"{_under_hundred(century)} {_under_hundred(rest)[:-1]}ies"
    if rest < 10:
        return f"{_under_hundred(century)} oh {ONES[rest]}"
    return f"{_under_hundred(century)} {_under_hundred(rest)}"


def expand_years(text: str, protect: int = 0) -> str:
    def pair(match: re.Match) -> str:
        if match.start() < protect:
            return match.group()
        year, plural = int(match.group(1)), bool(match.group(2))
        before, after = text[:match.start()], text[match.end():]
        if MONEY_BEFORE.search(before):
            return match.group()
        if plural:
            if year % 10:                        
                return match.group()
        elif not (CUE_BEFORE.search(before) or CUE_AFTER.match(after)):
            return match.group()
        return say_year(year, plural)

    return YEARLIKE.sub(pair, text)


def expand_identifiers(text: str, hindi: bool, protect: int = 0) -> str:
    table = HINDI_DIGITS if hindi else ENGLISH_DIGITS

    def spell(match: re.Match) -> str:
        if match.start() < protect:
            return match.group()
        digits = re.sub(r"\D", "", match.group())
        if 1900 <= int(digits) <= 2100:          
            return match.group()
        return " ".join(table[d] for d in digits)

    return IDENTIFIER.sub(spell, text)


def verbalize(text: str, hindi: bool, protect: int = 0) -> str:
    """Rewrites everything before `protect` untouched, so a carried-over tail
    can be sliced back off unchanged."""
    text = expand_identifiers(text, hindi, protect)
    # Hindi reads 2025 as do hazaar pachchees on its own, which is how it is
    # said — only English needs the pairing.
    return text if hindi else expand_years(text, protect)


# A cue can land in one chunk and its year in the next, so the tail of what was
# already spoken is carried forward as lookbehind — long enough for "in the ".
CONTEXT = 32


async def expand_stream(text: AsyncIterable[str], hindi: bool = False) -> AsyncGenerator[str, None]:
    """Expands across chunk boundaries — a phone number can arrive in pieces.

    Only the trailing digit run is buffered, so text flows to TTS with no
    added latency for ordinary prose.
    """
    buffer = ""
    carry = ""

    async for chunk in text:
        buffer += chunk
        hindi = hindi or bool(DEVANAGARI.search(buffer))

        match = UNFINISHED.search(buffer)
        cut = match.start() if match else len(buffer)
        if cut:
            spoken = carry + buffer[:cut]
            yield verbalize(spoken, hindi, protect=len(carry))[len(carry):]
            carry = spoken[-CONTEXT:]
        buffer = buffer[cut:]

    if buffer:
        yield verbalize(carry + buffer, hindi, protect=len(carry))[len(carry):]
