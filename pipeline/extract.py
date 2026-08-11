import re, sys, yaml, httpx, trafilatura

from pathlib import Path
from urllib.parse import urlparse, urljoin
from lxml import html as lxml_html

def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "page"

def is_allowed(url:str, domain: str, exclude: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.netloc != domain:
        return False
    return not any(re.search(pattern, url) for pattern in exclude)