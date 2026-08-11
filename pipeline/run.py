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
    meta = json.loads(path.read_text()) if path.exists() else {}
    meta.update(fields)
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


async def build_pack(url: str) -> str:
    pack_id = pack_id_for(url)
    pack_dir = PACKS_DIR / pack_id
    (pack_dir / "build").mkdir(parents=True, exist_ok=True)

    write_meta(pack_dir, pack_id=pack_id, source_url=url,
               created_at=time.time(), tier=0, error=None)

    print(f"pack {pack_id}  ←  {url}")

    started = time.monotonic()
    result = await crawl(url, pack_dir / "raw", CrawlLimits(max_pages=25),
                         on_progress=lambda n, total: print(f"  page {n}/{total}"))
    print(f"  crawl: {result['pages']} pages in {time.monotonic() - started:.1f}s")

    if result["error"]:
        write_meta(pack_dir, error=result["error"])
        print(f"  FAILED: {result['error']}")
        return pack_id

    chunks = build_chunks(pack_dir)
    write_meta(pack_dir, pages=result["pages"], chunks=len(chunks))

    lengths = sorted(len(c["source"]) for c in chunks)
    print(f"  chunks: {len(chunks)}")
    print(f"  chars:  min {lengths[0]} / median {lengths[len(lengths)//2]} / max {lengths[-1]}")
    return pack_id


if __name__ == "__main__":
    asyncio.run(build_pack(sys.argv[1]))