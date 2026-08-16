"""Builds a pack end to end: extract -> chunk -> embed.

No LLM runs here. Chunks are indexed in their original language and shaped
into speech at answer time, so build cost is O(pages) rather than
O(chunks x languages).

Every stage writes its progress into the pack's meta.json, so a caller that
did not start the build (the API) can still report where it is.
"""

import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

from pipeline.chunk import build_chunks
from pipeline.embed import build_vectors
from pipeline.extract import CrawlLimits, crawl, extract_pdf, normalize_domain

PACKS_DIR = Path("packs")

# Stages a build passes through, in order. "ready" and "failed" are terminal.
STAGES = ["extracting", "chunking", "embedding", "ready"]
IN_PROGRESS = set(STAGES[:-1])


def is_pdf_source(source: str) -> bool:
    return source.lower().endswith(".pdf")


def pack_id_for(source: str) -> str:
    """Same source always maps to the same pack, so rebuilds reuse the directory."""
    key = Path(source).stem if is_pdf_source(source) else normalize_domain(source)
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def subject_for(source: str) -> str:
    return Path(source).stem if is_pdf_source(source) else normalize_domain(source)


def meta_path(pack_id: str) -> Path:
    return PACKS_DIR / pack_id / "meta.json"


def has_raw(pack_dir: Path) -> bool:
    return any((pack_dir / "raw").glob("*.md"))


def read_meta(pack_id: str) -> dict:
    path = meta_path(pack_id)
    if not path.exists():
        return {}
    meta = json.loads(path.read_text(encoding="utf-8"))
    if not meta.get("stage"):
        meta = _describe_existing(pack_id, meta)

    # A pack from the translated-corpus era claims to be ready but has no
    # single index, and would only fail when a call tried to load it.
    if meta["stage"] == "ready" and not (PACKS_DIR / pack_id / "build" / "index.json").exists():
        return meta | {"stage": "incomplete", "vectors": 0}
    return meta


def _describe_existing(pack_id: str, meta: dict) -> dict:
    """Packs built before the stages existed: read their state off the disk.

    Per-language vectors are the old translated layout — those packs need a
    rebuild, which is now cheap, so they are reported as incomplete.
    """
    index_path = PACKS_DIR / pack_id / "build" / "index.json"
    vectors = len(json.loads(index_path.read_text(encoding="utf-8"))) if index_path.exists() else 0

    source = meta.get("source") or meta.get("source_url") or ""
    return meta | {
        "pack_id": pack_id,
        "source": source,
        "subject": meta.get("subject") or (subject_for(source) if source else pack_id),
        "stage": "ready" if vectors else "incomplete",
        "vectors": vectors,
    }


def write_meta(pack_id: str, **fields) -> dict:
    path = meta_path(pack_id)
    meta = read_meta(pack_id)
    meta.update(fields, pack_id=pack_id, updated_at=time.time())
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def list_packs() -> list[dict]:
    if not PACKS_DIR.exists():
        return []
    packs = [read_meta(path.name) for path in PACKS_DIR.iterdir() if path.is_dir()]
    return sorted((p for p in packs if p.get("pack_id")),
                  key=lambda p: p.get("created_at", 0), reverse=True)


async def build_pack(source: str, max_pages: int = 40, verbose: bool = False) -> dict:
    pack_id = pack_id_for(source)
    pack_dir = PACKS_DIR / pack_id
    (pack_dir / "build").mkdir(parents=True, exist_ok=True)

    def stage(name: str, **fields) -> None:
        write_meta(pack_id, stage=name, **fields)
        if verbose:
            print(f"  {name} {fields or ''}")

    def fail(reason: str) -> dict:
        if verbose:
            print(f"  FAILED: {reason}")
        return write_meta(pack_id, stage="failed", error=reason)

    write_meta(pack_id, source=source, subject=subject_for(source),
               created_at=time.time(), error=None, pages=0, chunks=0)

    if verbose:
        print(f"pack {pack_id}  <-  {source}")

    try:
        stage("extracting")
        if has_raw(pack_dir) and is_pdf_source(source) and not Path(source).exists():
            # The upload is gone but its markdown is not — rebuild from what we have.
            stage("extracting", note="source file missing, reusing extracted markdown")
        elif is_pdf_source(source):
            if not Path(source).exists():
                return fail(f"file not found: {source}")
            await asyncio.to_thread(extract_pdf, source, pack_dir / "raw")
        else:
            result = await crawl(source, pack_dir / "raw", CrawlLimits(max_pages=max_pages),
                                 on_progress=lambda n, _total: stage("extracting", pages=n))
            if result["error"]:
                return fail(result["error"])
            write_meta(pack_id, pages=result["pages"])

        stage("chunking")
        chunks = await asyncio.to_thread(build_chunks, pack_dir)
        if not chunks:
            return fail("no usable chunks produced")

        stage("embedding", chunks=len(chunks))
        vectors = await asyncio.to_thread(build_vectors, pack_dir)
        if not vectors:
            return fail("no vectors written")

        return write_meta(pack_id, stage="ready", vectors=vectors, error=None)

    except Exception as error:  # a build must never leave the pack stuck mid-stage
        return fail(f"{type(error).__name__}: {error}")


if __name__ == "__main__":
    source = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    meta = asyncio.run(build_pack(source, max_pages=max_pages, verbose=True))
    print(json.dumps({k: meta.get(k) for k in
                      ("pack_id", "stage", "pages", "chunks", "vectors", "error")}, indent=2))
