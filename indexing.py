from collections import deque

import chromadb
import httpx

import crawling
import openapi
from parsing import chunk, parse


async def index_page(collection: chromadb.Collection, url: str) -> str:
    response = await crawling.fetch(url)
    if response is None:
        return f"Failed to fetch {url}"
    indexed, is_openapi, swagger_specs = await index_response(collection, url, response)
    if not indexed:
        return f"No content extracted from {url}"
    kind = "operations" if is_openapi else "chunks"
    count = len(collection.get(where={"source_url": url})["ids"])
    msg = f"Indexed {count} {kind} from {url}"
    for spec_url in swagger_specs:
        op_count = len(collection.get(where={"source_url": spec_url})["ids"])
        msg += f"\n  + {op_count} operations from {spec_url}"
    return msg


async def index_tree(
    collection: chromadb.Collection,
    url: str,
    max_depth: int = 2,
    force: bool = False,
    log=None,
) -> str:
    visited: set[str] = set()
    # Pages discovered via plain-text/markdown links are treated as leaves:
    # they are indexed but their HTML links are not followed. This prevents
    # the combinatorial explosion when starting from llms.txt-style files
    # that list hundreds of doc pages, each with many navigation links.
    markdown_discovered: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(url, 0)])
    indexed, skipped, failed = 0, 0, 0

    while queue:
        current_url, depth = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)
        is_leaf = current_url in markdown_discovered

        if not force and is_indexed(collection, current_url):
            skipped += 1
            if log:
                await log(f"[skipped] {current_url}")
            if not is_leaf and depth < max_depth:
                response = await crawling.fetch(current_url)
                if response:
                    if crawling.is_html(response):
                        crawling.enqueue_links(response.text, current_url, depth, visited, queue)
                    elif crawling.is_plain_text(response):
                        crawling.enqueue_markdown_links(response.text, depth, visited, queue, markdown_discovered)
            continue

        response = await crawling.fetch(current_url)
        if response is None:
            failed += 1
            if log:
                await log(f"[failed] {current_url}")
            continue

        try:
            ok, is_openapi, _ = await index_response(collection, current_url, response)
        except Exception:
            failed += 1
            if log:
                await log(f"[failed] {current_url}")
            continue

        if ok:
            indexed += 1
            if log:
                await log(f"[indexed] {current_url}")

        if not is_leaf and depth < max_depth and not is_openapi:
            if crawling.is_html(response):
                crawling.enqueue_links(response.text, current_url, depth, visited, queue)
            elif crawling.is_plain_text(response):
                crawling.enqueue_markdown_links(response.text, depth, visited, queue, markdown_discovered)

    return f"Indexed {indexed} pages ({skipped} skipped, {failed} failed) starting from {url}"


def list_indexed_pages(collection: chromadb.Collection) -> list[dict]:
    if collection.count() == 0:
        return []
    counts: dict[str, int] = {}
    openapi_urls: set[str] = set()
    batch_size = 500
    offset = 0
    while True:
        result = collection.get(limit=batch_size, offset=offset, include=["metadatas"])
        metadatas = result["metadatas"]
        if not metadatas:
            break
        for meta in metadatas:
            url = meta.get("source_url", "unknown")
            counts[url] = counts.get(url, 0) + 1
            if meta.get("is_openapi"):
                openapi_urls.add(url)
        if len(metadatas) < batch_size:
            break
        offset += batch_size
    return [
        {"url": url, "chunks": n, "is_openapi": url in openapi_urls}
        for url, n in sorted(counts.items())
    ]


def clear_index(collection: chromadb.Collection) -> str:
    count = collection.count()
    if count == 0:
        return "Index already empty."
    batch_size = 500
    while True:
        batch = collection.get(limit=batch_size, include=[])
        if not batch["ids"]:
            break
        collection.delete(ids=batch["ids"])
    return f"Deleted {count} documents from index."


def is_indexed(collection: chromadb.Collection, url: str) -> bool:
    return bool(collection.get(where={"source_url": url})["ids"])


def upsert(
    collection: chromadb.Collection,
    documents: list[str],
    ids: list[str],
    metadatas: list[dict],
    url: str,
) -> bool:
    if not documents:
        return False
    existing = collection.get(where={"source_url": url})
    if existing["ids"]:
        stale = set(existing["ids"]) - set(ids)
        if stale:
            collection.delete(ids=list(stale))
    collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
    return True


async def index_response(
    collection: chromadb.Collection, url: str, response: httpx.Response
) -> tuple[bool, bool, list[str]]:
    if openapi.is_openapi(response):
        docs, ids, metas = openapi.openapi_documents(response.json(), url)
        return upsert(collection, docs, ids, metas, url), True, []
    if crawling.is_plain_text(response):
        chunks = chunk(response.text)
        ids = [f"{url}::{i}" for i in range(len(chunks))]
        metas = [{"source_url": url} for _ in chunks]
        return upsert(collection, chunks, ids, metas, url), False, []
    html = response.text
    swagger_spec_urls = []
    for swagger_ui_url in openapi.extract_swagger_ui_links(html, url):
        for spec_url in await openapi.resolve_swagger_spec_urls(swagger_ui_url):
            spec_response = await crawling.fetch(spec_url)
            if spec_response and openapi.is_openapi(spec_response):
                docs, ids, metas = openapi.openapi_documents(spec_response.json(), spec_url)
                if upsert(collection, docs, ids, metas, spec_url):
                    swagger_spec_urls.append(spec_url)
    chunks = chunk(parse(html))
    ids = [f"{url}::{i}" for i in range(len(chunks))]
    metas = [{"source_url": url} for _ in chunks]
    return upsert(collection, chunks, ids, metas, url), False, swagger_spec_urls
