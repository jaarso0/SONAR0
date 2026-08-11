"""Convert raw markdown files into chunk records."""

from pathlib import Path


def chunk_pack(pack_dir: Path) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for path in sorted((pack_dir / "raw").glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            chunks.append({"source": path.name, "text": text})
    return chunks
