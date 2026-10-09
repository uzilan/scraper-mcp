import re
from collections import deque
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


async def discover_links(url: str, max_depth: int = 2, log=None) -> list[str]:
    visited: set[str] = set()
    markdown_discovered: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(url, 0)])
    found: list[str] = []

    while queue:
        current_url, depth = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)
        found.append(current_url)
        if log:
            await log(current_url)

        is_leaf = current_url in markdown_discovered
        if not is_leaf and depth < max_depth:
            response = await fetch(current_url)
            if response:
                if is_html(response):
                    enqueue_links(response.text, current_url, depth, visited, queue)
                elif is_plain_text(response):
                    enqueue_markdown_links(response.text, depth, visited, queue, markdown_discovered)

    return found


def extract_markdown_links(text: str) -> list[str]:
    return re.findall(r'\[[^\]]*\]\((https?://[^)]+)\)', text)


def enqueue_markdown_links(
    text: str, depth: int, visited: set, queue: deque, markdown_discovered: set | None = None
) -> None:
    for link in extract_markdown_links(text):
        if link not in visited:
            if markdown_discovered is not None:
                markdown_discovered.add(link)
            queue.append((link, depth + 1))


def enqueue_links(html: str, base_url: str, depth: int, visited: set, queue: deque) -> None:
    for link in extract_links(html, base_url):
        if link not in visited:
            queue.append((link, depth + 1))


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["footer", "header"]):
        tag.decompose()
    base = urlparse(base_url)
    links = []
    for tag in soup.find_all("a", href=True):
        url = urljoin(base_url, tag["href"]).split("#")[0]
        parsed = urlparse(url)
        if parsed.netloc == base.netloc and parsed.scheme in ("http", "https"):
            links.append(url)
    return list(dict.fromkeys(links))


async def fetch(url: str) -> httpx.Response | None:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response
    except Exception:
        return None


def is_html(response: httpx.Response) -> bool:
    ct = response.headers.get("content-type", "")
    return "text/html" in ct or (not ct)


def is_plain_text(response: httpx.Response) -> bool:
    ct = response.headers.get("content-type", "")
    return "text/plain" in ct or "text/markdown" in ct
