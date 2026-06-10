import re
from contextlib import asynccontextmanager
from pathlib import Path

import chromadb
import chromadb.utils.embedding_functions as ef
from mcp.server.fastmcp import FastMCP

CHROMA_PATH = Path(__file__).parent / "data" / "chroma"
VALID_NAME = re.compile(r"^[a-zA-Z0-9_-]{3,63}$")

embed_fn = ef.DefaultEmbeddingFunction()

_chroma_client: chromadb.api.ClientAPI | None = None
_current_collection: chromadb.Collection | None = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    global _chroma_client
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    yield {}


mcp = FastMCP("scraper", lifespan=lifespan)


def _create_namespace(client: chromadb.api.ClientAPI, name: str) -> str:
    if not VALID_NAME.match(name):
        return f"Invalid name '{name}'. Use 3-63 chars, alphanumeric + hyphens/underscores only."
    client.get_or_create_collection(name, embedding_function=embed_fn)
    return f"Namespace '{name}' ready."


def _use_namespace(client: chromadb.api.ClientAPI, name: str) -> str:
    global _current_collection
    try:
        _current_collection = client.get_collection(name, embedding_function=embed_fn)
        return f"Using namespace '{name}'."
    except Exception:
        return f"Namespace '{name}' does not exist. Call create_namespace('{name}') first."


def _delete_namespace(client: chromadb.api.ClientAPI, name: str) -> str:
    global _current_collection
    try:
        client.delete_collection(name)
    except Exception:
        return f"Namespace '{name}' does not exist."
    if _current_collection is not None and _current_collection.name == name:
        _current_collection = None
    return f"Namespace '{name}' deleted."


def _list_namespaces(client: chromadb.api.ClientAPI) -> list[str]:
    return [c.name for c in client.list_collections()]


def _current_namespace() -> str:
    if _current_collection is None:
        return "No namespace selected."
    return _current_collection.name


@mcp.tool()
def create_namespace(name: str) -> str:
    """Create a new namespace. Does not switch to it."""
    return _create_namespace(_chroma_client, name)


@mcp.tool()
def use_namespace(name: str) -> str:
    """Set the active namespace for this session."""
    return _use_namespace(_chroma_client, name)


@mcp.tool()
def delete_namespace(name: str) -> str:
    """Delete a namespace and all its indexed data."""
    return _delete_namespace(_chroma_client, name)


@mcp.tool()
def list_namespaces() -> list[str]:
    """List all existing namespaces."""
    return _list_namespaces(_chroma_client)


@mcp.tool()
def current_namespace() -> str:
    """Return the active namespace name, or a message if none is set."""
    return _current_namespace()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
