"""File-backed retrieval helpers for built packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FileRetriever:
    def __init__(self, pack_dir: Path) -> None:
        self.pack_dir = pack_dir
        self.chunks_path = pack_dir / "build" / "chunks.json"

    def load_chunks(self) -> list[dict[str, Any]]:
        if not self.chunks_path.exists():
            return []
        return json.loads(self.chunks_path.read_text(encoding="utf-8"))

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        terms = query.lower().split()
        scored: list[tuple[int, dict[str, Any]]] = []
        for chunk in self.load_chunks():
            text = str(chunk.get("text", "")).lower()
            score = sum(text.count(term) for term in terms)
            if score:
                scored.append((score, chunk))
        return [chunk for _, chunk in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]


def speculative_search(retriever: FileRetriever, query: str) -> list[dict[str, Any]]:
    return retriever.search(query)
