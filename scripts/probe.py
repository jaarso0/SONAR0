"""Scores questions against a pack, to see what the agent would be given.

    uv run python scripts/probe.py <pack_id> "question" "another question"

With no questions it runs a bilingual pair against the same index — the point
being that both should reach the same chunks.
"""

import sys
from pathlib import Path

from worker.retrieval import FileRetriever

sys.stdout.reconfigure(encoding="utf-8")   # the questions are half Devanagari

DEFAULT_QUESTIONS = [
    "what are the opening hours",
    "यह कहाँ स्थित है",
    "how much does it cost",
    "कीमत कितनी है",
]

pack_id = sys.argv[1]
questions = sys.argv[2:] or DEFAULT_QUESTIONS

retriever = FileRetriever(Path("packs") / pack_id)

for question in questions:
    print(f"\n{question}")
    for hit in retriever.search(question, k=3):
        print(f"  {hit['score']:.3f}  {hit['heading_path'][:40]:<42} "
              f"{hit['text'][:70].replace(chr(10), ' ')}")
