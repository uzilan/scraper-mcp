from contextlib import asynccontextmanager

from mcp.server.fastmcp import Context, FastMCP

import agent
import application
import namespaces


@asynccontextmanager
async def lifespan(server: FastMCP):
    namespaces.initialize_client()
    yield {}
    await agent.shutdown()


mcp = FastMCP("scraper", lifespan=lifespan)


@mcp.tool()
def create_namespace(name: str) -> str:
    """Create a new namespace and switch to it immediately."""
    return application.create_namespace(name)


@mcp.tool()
def use_namespace(name: str) -> str:
    """Set the active namespace for this session."""
    return application.use_namespace(name)


@mcp.tool()
def delete_namespace(name: str) -> str:
    """Delete a namespace and all its indexed data."""
    return application.delete_namespace(name)


@mcp.tool()
def list_namespaces() -> list[str]:
    """List all existing namespaces."""
    return application.list_namespaces()


@mcp.tool()
def current_namespace() -> str:
    """Return the active namespace name, or a message if none is set."""
    return application.current_namespace()


@mcp.tool()
async def index_page(url: str) -> str:
    """Fetch a documentation page and add it to the current namespace index."""
    return await application.index_page(url)


@mcp.tool()
async def index_tree(url: str, ctx: Context, max_depth: int = 2, force: bool = False) -> str:
    """Fetch a documentation site and recursively index all pages on the same domain."""
    return await application.index_tree(url, max_depth, force, ctx.info)


@mcp.tool()
async def discover_links(url: str, max_depth: int = 2) -> list[str]:
    """Discover all pages reachable from a URL within max_depth hops on the same domain."""
    return await application.discover_links(url, max_depth)


@mcp.tool()
def list_indexed_pages() -> list[dict]:
    """List all pages currently in the active namespace index."""
    return application.list_indexed_pages()


@mcp.tool()
def clear_index() -> str:
    """Delete all documents from the active namespace index."""
    return application.clear_index()


@mcp.tool()
def upload_document(filename: str, content_b64: str) -> str:
    """Upload a document to the current namespace and index it for search. content_b64 must be base64-encoded file content."""
    return application.upload_document(filename, content_b64)


@mcp.tool()
def list_documents() -> list[dict]:
    """List uploaded documents in the current namespace."""
    return application.list_documents()


@mcp.tool()
def delete_document(filename: str) -> str:
    """Delete an uploaded document from the current namespace and remove it from the index."""
    return application.delete_document(filename)


@mcp.tool()
def search_docs(query: str, n_results: int = 5) -> dict:
    """Search the active namespace. Returns relevant chunks with source URLs and a deduplicated references list."""
    return application.search_docs(query, n_results)


@mcp.tool()
async def ask(query: str, n_results: int = 5) -> dict:
    """Ask a question and get a synthesized answer with cited sources from the active namespace."""
    return await application.ask(query, n_results)
