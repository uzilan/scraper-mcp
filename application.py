import documents
import indexing
import namespaces
import search
from crawling import discover_links
from namespaces import (
    create_namespace,
    current_namespace,
    delete_namespace,
    list_namespaces,
    use_namespace,
)


async def index_page(url: str) -> str:
    if namespaces.current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    return await indexing.index_page(namespaces.current_collection, url)


async def index_tree(url: str, max_depth: int = 2, force: bool = False, log=None) -> str:
    if namespaces.current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    return await indexing.index_tree(namespaces.current_collection, url, max_depth, force, log)


def search_docs(query: str, n_results: int = 5) -> dict:
    if namespaces.current_collection is None:
        return {"error": "No namespace selected. Call use_namespace(name) first."}
    if namespaces.current_collection.count() == 0:
        return {"error": "Namespace is empty. Call index_page(url) first."}
    return search.search_docs(namespaces.current_collection, query, n_results)


async def ask(query: str, n_results: int = 5) -> dict:
    if namespaces.current_collection is None:
        return {"error": "No namespace selected. Call use_namespace(name) first."}
    if namespaces.current_collection.count() == 0:
        return {"error": "Namespace is empty. Call index_page(url) first."}
    return await search.ask(namespaces.current_collection, query, n_results)

def list_indexed_pages() -> list[dict]:
    """List all pages currently in the active namespace index."""
    if namespaces.current_collection is None:
        return []
    return indexing.list_indexed_pages(namespaces.current_collection)


def clear_index() -> str:
    """Delete all documents from the active namespace index."""
    if namespaces.current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    return indexing.clear_index(namespaces.current_collection)


def upload_document(filename: str, content_b64: str) -> str:
    """Upload a document to the current namespace and index it for search. content_b64 must be base64-encoded file content."""
    import base64
    if namespaces.current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    namespace = namespaces.current_collection.name
    folder = namespaces.UPLOADS_PATH / namespace
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    path.write_bytes(base64.b64decode(content_b64))
    return documents.index_file(namespaces.current_collection, namespace, path)


def list_documents() -> list[dict]:
    """List uploaded documents in the current namespace."""
    if namespaces.current_collection is None:
        return []
    return documents.list_documents(namespaces.current_collection.name)


def delete_document(filename: str) -> str:
    """Delete an uploaded document from the current namespace and remove it from the index."""
    if namespaces.current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    return documents.delete_document(namespaces.current_collection, namespaces.current_collection.name, filename)
