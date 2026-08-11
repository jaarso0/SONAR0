import json
import sys
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "intfloat/multilingual-e5-large"
DIMENSIONS = 1024

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def passage_text(chunk: dict, lang: str) -> str:
    """What actually gets embedded: heading for topic signal, spoken text for content."""
    return f"passage: {chunk['heading_path']}. {chunk['spoken'][lang]}"


def query_text(question: str) -> str:
    return f"query: {question}"


def embed_texts(texts: list[str]) -> np.ndarray:
    vectors = np.array(list(get_model().embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-9, None)


def build_vectors(pack_dir: Path, languages: list[str]) -> dict[str, int]:
    chunks = json.loads((pack_dir / "build" / "chunks.json").read_text(encoding="utf-8"))
    counts = {}

    for lang in languages:
        present = [c for c in chunks if lang in c.get("spoken", {})]
        if not present:
            print(f"  {lang}: no spoken text, skipping")
            continue

        vectors = embed_texts([passage_text(c, lang) for c in present])
        vectors.tofile(pack_dir / "build" / f"vectors.{lang}.bin")

        index_path = pack_dir / "build" / f"index.{lang}.json"
        index_path.write_text(json.dumps([c["id"] for c in present]), encoding="utf-8")

        counts[lang] = len(present)
        print(f"  {lang}: {len(present)} vectors x {vectors.shape[1]} dims "
              f"({vectors.nbytes / 1024:.0f} KB)")

    return counts


if __name__ == "__main__":
    pack_dir = Path("packs") / sys.argv[1]
    languages = sys.argv[2].split(",") if len(sys.argv) > 2 else ["en-IN", "hi-IN"]
    build_vectors(pack_dir, languages)