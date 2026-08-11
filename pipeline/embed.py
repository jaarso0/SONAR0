"""Embedding build step placeholder."""

from pathlib import Path


def build_embeddings(pack_dir: Path, lang: str = "en") -> Path:
    output_path = pack_dir / "build" / f"vectors.{lang}.bin"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.touch()
    return output_path
