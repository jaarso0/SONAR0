"""Pipeline runner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.chunk import chunk_pack
from pipeline.embed import build_embeddings
from pipeline.validate import validate_pack


def run(url: str, pack_id: str = "example_pack") -> Path:
    pack_dir = Path("packs") / pack_id
    (pack_dir / "raw").mkdir(parents=True, exist_ok=True)
    (pack_dir / "build").mkdir(parents=True, exist_ok=True)
    (pack_dir / "meta.json").write_text(json.dumps({"url": url}, indent=2), encoding="utf-8")
    errors = validate_pack(pack_dir)
    if errors:
        raise RuntimeError("; ".join(errors))
    chunks = chunk_pack(pack_dir)
    (pack_dir / "build" / "chunks.json").write_text(json.dumps(chunks, indent=2), encoding="utf-8")
    build_embeddings(pack_dir)
    return pack_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--pack-id", default="example_pack")
    args = parser.parse_args()
    print(run(args.url, args.pack_id))


if __name__ == "__main__":
    main()
