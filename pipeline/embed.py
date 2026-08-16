"""Embeds chunk source text into one index.

multilingual-e5 puts every language in a shared vector space, so a Hindi
question retrieves an English passage directly — one index serves every
language, and no part of the corpus is translated ahead of time.
"""

import json
import sys
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "intfloat/multilingual-e5-large"

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def passage_text(chunk: dict) -> str:
    """Heading for topic signal, body for content — e5 wants the prefix."""
    return f"passage: {chunk['heading_path']}. {chunk['source']}"


def query_text(question: str) -> str:
    return f"query: {question}"


def embed_texts(texts: list[str]) -> np.ndarray:
    vectors = np.array(list(get_model().embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-9, None)


def build_vectors(pack_dir: Path) -> int:
    build_dir = pack_dir / "build"
    chunks = json.loads((build_dir / "chunks.json").read_text(encoding="utf-8"))
    if not chunks:
        return 0

    vectors = embed_texts([passage_text(c) for c in chunks])
    vectors.tofile(build_dir / "vectors.bin")
    (build_dir / "index.json").write_text(
        json.dumps([c["id"] for c in chunks]), encoding="utf-8")

    print(f"  {len(chunks)} vectors x {vectors.shape[1]} dims "
          f"({vectors.nbytes / 1024:.0f} KB)")
    return len(chunks)


if __name__ == "__main__":
    build_vectors(Path("packs") / sys.argv[1])
