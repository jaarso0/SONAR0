import json
from pathlib import Path

import numpy as np

from embedding import embed_texts, query_text


class FileRetriever:
    """Loads one pack into memory. Brute-force cosine — no index needed at this size."""

    def __init__(self, pack_dir: Path, languages: list[str]):
        self.chunks = {c["id"]: c
                       for c in json.loads((pack_dir / "build" / "chunks.json")
                                           .read_text(encoding="utf-8"))}
        self.ids: dict[str, list[str]] = {}
        self.matrices: dict[str, np.ndarray] = {}

        for lang in languages:
            index_path = pack_dir / "build" / f"index.{lang}.json"
            vectors_path = pack_dir / "build" / f"vectors.{lang}.bin"
            if not index_path.exists():
                continue
            ids = json.loads(index_path.read_text(encoding="utf-8"))
            matrix = np.fromfile(vectors_path, dtype=np.float32).reshape(len(ids), -1)
            self.ids[lang] = ids
            self.matrices[lang] = matrix

    def search(self, question: str, lang: str, k: int = 3) -> list[dict]:
        if lang not in self.matrices:
            lang = next(iter(self.matrices))

        query_vector = embed_texts([query_text(question)])[0]
        scores = self.matrices[lang] @ query_vector
        top = np.argsort(-scores)[:k]

        return [{"id": self.ids[lang][i],
                 "score": float(scores[i]),
                 "text": self.chunks[self.ids[lang][i]]["spoken"][lang]}
                for i in top]