import json
from pathlib import Path

import numpy as np

from pipeline.embed import embed_texts, query_text


class FileRetriever:
    """Loads one pack into memory. Brute-force cosine — no index needed at this size.

    Chunks are stored in their original language; the shared embedding space
    means a question in any language scores against all of them.
    """

    def __init__(self, pack_dir: Path):
        build_dir = pack_dir / "build"
        meta_path = pack_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

        self.pack_id = pack_dir.name
        self.subject = (meta.get("subject") or meta.get("source")
                        or meta.get("source_url") or "this business")

        index_path = build_dir / "index.json"
        if not index_path.exists():
            raise RuntimeError(
                f"pack {self.pack_id} has no index — rebuild it with pipeline.run")

        self.chunks = {c["id"]: c for c in
                       json.loads((build_dir / "chunks.json").read_text(encoding="utf-8"))}
        self.ids = json.loads(index_path.read_text(encoding="utf-8"))
        self.matrix = np.fromfile(build_dir / "vectors.bin",
                                  dtype=np.float32).reshape(len(self.ids), -1)

        print(f">>> PACK {self.pack_id}  subject={self.subject}  chunks={len(self.ids)}")

    def search(self, question: str, k: int = 3, min_score: float = 0.0) -> list[dict]:
        scores = self.matrix @ embed_texts([query_text(question)])[0]
        top = np.argsort(-scores)[:k]

        return [{"id": self.ids[i],
                 "score": float(scores[i]),
                 "heading_path": self.chunks[self.ids[i]]["heading_path"],
                 "text": self.chunks[self.ids[i]]["source"]}
                for i in top if scores[i] >= min_score]
