import logging
from contextlib import asynccontextmanager
from pathlib import Path

import chromadb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import server

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if server._chroma_client is None:
        server.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        server._chroma_client = chromadb.PersistentClient(path=str(server.CHROMA_PATH))
    yield


app = FastAPI(title="Scraper MCP REST API", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_ERROR_MARKERS = (
    "Invalid name",
    "does not exist",
    "No namespace",
    "Failed to",
    "No content extracted",
)


def _raise_if_error(result: str) -> None:
    if any(marker in result for marker in _ERROR_MARKERS):
        raise HTTPException(status_code=400, detail=result)


class NamespaceBody(BaseModel):
    name: str


@app.post("/namespaces")
def create_namespace_route(body: NamespaceBody) -> str:
    result = server._create_namespace(server._chroma_client, body.name)
    _raise_if_error(result)
    return result


@app.get("/namespaces")
def list_namespaces_route() -> list[str]:
    return server._list_namespaces(server._chroma_client)


@app.delete("/namespaces/{name}")
def delete_namespace_route(name: str) -> str:
    result = server._delete_namespace(server._chroma_client, name)
    _raise_if_error(result)
    return result


@app.post("/namespaces/{name}/use")
def use_namespace_route(name: str) -> str:
    result = server._use_namespace(server._chroma_client, name)
    _raise_if_error(result)
    return result


@app.get("/namespaces/current")
def current_namespace_route() -> str:
    return server._current_namespace()


class IndexPageBody(BaseModel):
    url: str


class IndexTreeBody(BaseModel):
    url: str
    max_depth: int = 2
    force: bool = False


@app.post("/index/page")
async def index_page_route(body: IndexPageBody) -> str:
    result = await server._index_page_tool(body.url)
    _raise_if_error(result)
    return result


@app.post("/index/tree")
async def index_tree_route(body: IndexTreeBody) -> str:
    # log=None: REST clients cannot receive streaming progress updates
    result = await server._index_tree_tool(body.url, body.max_depth, body.force)
    _raise_if_error(result)
    return result


@app.get("/index/pages")
def list_indexed_pages_route() -> list[dict]:
    if server._current_collection is None:
        return []
    return server._list_indexed_pages(server._current_collection)


@app.delete("/index")
def clear_index_route() -> str:
    if server._current_collection is None:
        raise HTTPException(status_code=400, detail="No namespace selected. Call use_namespace first.")
    return server._clear_index(server._current_collection)


@app.get("/search")
def search_route(query: str, n_results: int = 5) -> dict:
    result = server._search_docs_tool(query, n_results)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/links")
async def discover_links_route(url: str, max_depth: int = 2) -> list[str]:
    return await server._discover_links(url, max_depth)


_UI_DIST = Path(__file__).parent / "ui" / "dist"
if _UI_DIST.exists():
    app.mount("/ui", StaticFiles(directory=_UI_DIST, html=True), name="ui")
else:
    _logger.warning("UI dist not found at %s — run 'npm run build' in ui/ to serve the frontend", _UI_DIST)
