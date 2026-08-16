import asyncio
import ipaddress
import re
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from lxml import html as lxml_html

MAX_PAGE_BYTES = 2_000_000
CONCURRENCY = 4
USER_AGENT = "sonar-pipeline/0.1"


@dataclass
class CrawlLimits:
    max_pages: int = 40
    max_seconds: float = 45.0
    exclude: list[str] = field(default_factory=lambda: [
        r"/blog/", r"/news", r"/careers", r"/privacy", r"/terms",
        r"grievance", r"return-policy", r"return_policy",
        r"shipping-policy", r"shipping_policy", r"refund", r"journal",
        r"\.(jpg|jpeg|png|gif|svg|zip|mp4|doc|docx)$", r"\?",
    ])

def normalize_url(url: str) -> str:
    url = url.split("#")[0]
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"

def normalize_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "index"


def is_safe_url(url: str) -> tuple[bool, str]:
    """Reject anything resolving to a private address. Applied to every URL, not just seeds."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, "only http and https are allowed"
    if not parsed.hostname:
        return False, "no hostname in url"
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False, "cannot resolve host"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, "resolves to a private address"
    return True, ""


def is_in_scope(url: str, domain: str, exclude: list[str]) -> bool:
    if normalize_domain(url) != domain:
        return False
    if any(re.search(pattern, url, re.I) for pattern in exclude):
        return False
    return is_safe_url(url)[0]


def find_links(html_text: str, base_url: str) -> list[str]:
    try:
        tree = lxml_html.fromstring(html_text)
    except Exception:
        return []
    return [normalize_url(urljoin(base_url, href)) for href in tree.xpath("//a/@href")]


def extract_markdown(html_text: str) -> str | None:
    return trafilatura.extract(
        html_text,
        output_format="markdown",
        include_links=False,
        include_tables=True,
        include_comments=False,
        favor_precision=True,
    )


def write_document(out_dir: Path, name: str, source_url: str, markdown: str) -> Path:
    path = out_dir / f"{name}.md"
    counter = 1
    while path.exists():
        path = out_dir / f"{name}-{counter}.md"
        counter += 1
    path.write_text(f"---\nsource_url: {source_url}\n---\n\n{markdown}\n", encoding="utf-8")
    return path


async def fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    if "html" not in response.headers.get("content-type", "").lower():
        return None
    if len(response.content) > MAX_PAGE_BYTES:
        return None
    return response.text


async def crawl(seed_url: str, out_dir: Path, limits: CrawlLimits,
                on_progress=None) -> dict:
    seed_url = normalize_url(seed_url) 
    safe, reason = is_safe_url(seed_url)
    if not safe:
        return {"pages": 0, "error": reason}

    domain = normalize_domain(seed_url)
    out_dir.mkdir(parents=True, exist_ok=True)

    queue: asyncio.Queue[str] = asyncio.Queue()
    await queue.put(seed_url)
    seen: set[str] = {seed_url}
    written = 0
    deadline = time.monotonic() + limits.max_seconds

    async with httpx.AsyncClient(
        timeout=15, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:

        async def worker():
            nonlocal written
            while written < limits.max_pages and time.monotonic() < deadline:
                try:
                    url = await asyncio.wait_for(queue.get(), timeout=3.0)
                except asyncio.TimeoutError:
                    return

                html_text = await fetch_page(client, url)
                if html_text is None:
                    queue.task_done()
                    continue

                markdown = extract_markdown(html_text)
                if markdown and len(markdown) > 200 and written < limits.max_pages:
                    written += 1
                    write_document(out_dir, slugify(urlparse(url).path), url, markdown)
                    if on_progress:
                        on_progress(written, limits.max_pages)

                for link in find_links(html_text, url):
                    if link not in seen and is_in_scope(link, domain, limits.exclude):
                        seen.add(link)
                        await queue.put(link)
                queue.task_done()

        await asyncio.gather(*[worker() for _ in range(CONCURRENCY)])

    if written == 0:
        return {"pages": 0, "error": "no readable pages found"}
    if written < 3:
        return {"pages": written,
                "error": "too little readable content — the site likely renders in the browser"}
    return {"pages": written, "error": None}


def extract_pdf(pdf_path: str, out_dir: Path) -> Path:
    import pymupdf4llm
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown = pymupdf4llm.to_markdown(pdf_path)
    return write_document(out_dir, slugify(Path(pdf_path).stem),
                          f"file://{pdf_path}", markdown)