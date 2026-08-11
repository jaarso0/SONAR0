import json
import re
import sys
from pathlib import Path

BAD_MAGNITUDES = ["लाख", "करोड़", "हजार", "हज़ार", "सौ"]

PHONE_PATTERN = re.compile(r"\b0?\d{5}[\s-]?\d{5}\b|\b\+?91[\s-]?\d{10}\b")
PINCODE_PATTERN = re.compile(r"\b\d{6}\b")


def find_digit_sequences(text: str) -> list[str]:
    """Only numbers that must be read digit-by-digit: phones and pincodes."""
    found = PHONE_PATTERN.findall(text) + PINCODE_PATTERN.findall(text)
    return [f for f in found if not (1900 <= int(re.sub(r"\D", "", f) or 0) <= 2100)]


def check_chunk(chunk: dict) -> list[str]:
    problems = []
    sequences = find_digit_sequences(chunk["source"])

    for lang, spoken in chunk.get("spoken", {}).items():
        if re.search(r"[*#|₹$•]", spoken):
            problems.append(f"{chunk['id']} {lang}: symbol survived")
        if re.search(r"\d", spoken):
            problems.append(f"{chunk['id']} {lang}: raw digits left unexpanded")

        if lang == "hi-IN":
            latin = re.findall(r"[A-Za-z]{4,}", spoken)
            if len(latin) > 2:
                problems.append(f"{chunk['id']} hi-IN: latin words {latin[:4]}")
            if sequences and any(word in spoken for word in BAD_MAGNITUDES):
                problems.append(
                    f"{chunk['id']} hi-IN: phone/pincode {sequences} read as a quantity")

    return problems


if __name__ == "__main__":
    pack_dir = Path("packs") / sys.argv[1]
    chunks = json.loads((pack_dir / "build" / "chunks.json").read_text(encoding="utf-8"))
    problems = [p for chunk in chunks for p in check_chunk(chunk)]
    for problem in problems:
        print(problem)
    print(f"\n{len(problems)} problems across {len(chunks)} chunks")