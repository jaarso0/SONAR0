import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

from pipeline.extract import CrawlLimits, crawl, normalize_domain
from pipeline.chunk import build_chunks

PACKS_DIR = Path("packs")


def pack_id_for(url: str) -> str:
    return hashlib.sha1(normalize_domain(url).encode()).hexdigest()[:12]


def write_meta(pack_dir: Path, **fields) -> None:
    path = pack_dir / "meta.json"
    meta = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    meta.update(fields)
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


async def build_pack(source: str, max_pages: int = 25) -> str:
    is_pdf = source.lower().endswith(".pdf")
    pack_id = (hashlib.sha1(Path(source).stem.encode()).hexdigest()[:12] if is_pdf
               else pack_id_for(source))

    pack_dir = PACKS_DIR / pack_id
    (pack_dir / "build").mkdir(parents=True, exist_ok=True)

    write_meta(pack_dir, pack_id=pack_id, source_url=source,
               created_at=time.time(), tier=0, error=None)

    print(f"pack {pack_id}  <-  {source}")

    if is_pdf:
        from pipeline.extract import extract_pdf
        path = extract_pdf(source, pack_dir / "raw")
        print(f"  extracted {path.name}")
    else:
        started = time.monotonic()
        result = await crawl(source, pack_dir / "raw", CrawlLimits(max_pages=max_pages),
                             on_progress=lambda n, total: print(f"  page {n}/{total}"))
        print(f"  crawl: {result['pages']} pages in {time.monotonic() - started:.1f}s")
        if result["error"]:
            write_meta(pack_dir, error=result["error"])
            print(f"  FAILED: {result['error']}")
            return pack_id
        write_meta(pack_dir, pages=result["pages"])

    chunks = build_chunks(pack_dir)
    write_meta(pack_dir, chunks=len(chunks))

    if not chunks:
        print("  no usable chunks produced")
        return pack_id

    lengths = sorted(len(c["source"]) for c in chunks)
    print(f"  chunks: {len(chunks)}")
    print(f"  chars:  min {lengths[0]} / median {lengths[len(lengths)//2]} / max {lengths[-1]}")
    return pack_id


if __name__ == "__main__":
    source = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    asyncio.run(build_pack(source, max_pages))