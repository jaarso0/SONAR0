import json
import re
from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

MAX_CHUNK_CHARS = 1200
MIN_CHUNK_CHARS = 80

_header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=True,
)
_overflow_splitter = RecursiveCharacterTextSplitter(
    chunk_size=MAX_CHUNK_CHARS,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " "],
)


BOILERPLATE = re.compile(
    r"no credit card|get started|book a demo|sign up free|©|all rights reserved",
    re.I,
)

def is_low_value(text: str) -> bool:
    if BOILERPLATE.search(text):
        return True
    words = text.split()
    if len(words) < 20:
        return True
    return sum(1 for w in words if w.isdigit() or "₹" in w or "$" in w) == 0 and len(words) < 30

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "section"


def read_document(path: Path) -> tuple[str, str]:
    """Returns (source_url, markdown_body), stripping the frontmatter we wrote."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n\n(.*)$", text, re.DOTALL)
    if not match:
        return "", text
    found = re.search(r"source_url:\s*(\S+)", match.group(1))
    return (found.group(1) if found else ""), match.group(2)


def chunk_document(markdown: str, doc_id: str, source_url: str) -> list[dict]:
    chunks = []
    counter = 0

    for section in _header_splitter.split_text(markdown):
        heading_path = " > ".join(v for v in section.metadata.values() if v) or doc_id.replace("-", " ")

        pieces = ([section] if len(section.page_content) <= MAX_CHUNK_CHARS
                  else _overflow_splitter.split_documents([section]))

        for piece in pieces:
            body = piece.page_content.strip()
            if len(body) < MIN_CHUNK_CHARS or is_low_value(body):
                continue
            chunks.append({
                "id": f"{doc_id}.{counter:03d}",
                "heading_path": heading_path,
                "source_url": source_url,
                "source": body,
                "spoken": {},
            })
            counter += 1

    return chunks


import hashlib

def build_chunks(pack_dir: Path) -> list[dict]:
    all_chunks: list[dict] = []
    seen_hashes: set[str] = set()

    for path in sorted((pack_dir / "raw").glob("*.md")):
        source_url, markdown = read_document(path)
        for chunk in chunk_document(markdown, path.stem, source_url):
            digest = hashlib.sha1(chunk["source"].encode()).hexdigest()
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            all_chunks.append(chunk)
    
    out_path = pack_dir / "build" / "chunks.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    return all_chunks