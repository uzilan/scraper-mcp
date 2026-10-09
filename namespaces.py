import re
from pathlib import Path

import chromadb
import chromadb.utils.embedding_functions as ef

CHROMA_PATH = Path(__file__).parent / "data" / "chroma"
UPLOADS_PATH = Path(__file__).parent / "data" / "uploads"
VALID_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,61}[a-zA-Z0-9]$")

embed_fn = ef.DefaultEmbeddingFunction()
chroma_client: chromadb.api.ClientAPI | None = None
current_collection: chromadb.Collection | None = None


def initialize_client() -> None:
    global chroma_client
    if chroma_client is None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))


def create_namespace(name: str) -> str:
    global current_collection
    if not VALID_NAME.match(name):
        return f"Invalid name '{name}'. Use 3-63 chars, alphanumeric + hyphens/underscores only."
    current_collection = chroma_client.get_or_create_collection(
        name, embedding_function=embed_fn, configuration={"hnsw": {"space": "cosine"}}
    )
    return f"Namespace '{name}' created and is now active."


def use_namespace(name: str) -> str:
    global current_collection
    try:
        current_collection = chroma_client.get_collection(name, embedding_function=embed_fn)
        return f"Using namespace '{name}'."
    except Exception:
        return f"Namespace '{name}' does not exist. Call create_namespace('{name}') first."


def delete_namespace(name: str) -> str:
    import shutil
    global current_collection
    try:
        chroma_client.delete_collection(name)
    except Exception:
        return f"Namespace '{name}' does not exist."
    if current_collection is not None and current_collection.name == name:
        current_collection = None
    uploads_folder = UPLOADS_PATH / name
    if uploads_folder.exists():
        shutil.rmtree(uploads_folder)
    return f"Namespace '{name}' deleted."


def list_namespaces() -> list[str]:
    return [c.name for c in chroma_client.list_collections()]


def current_namespace() -> str:
    if current_collection is None:
        return "No namespace selected."
    return current_collection.name
