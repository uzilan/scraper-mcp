from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import server

app = FastAPI(title="Scraper MCP REST API")

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
