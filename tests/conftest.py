import chromadb
import pytest
import server


@pytest.fixture(autouse=True)
def reset_state():
    client = chromadb.EphemeralClient()
    for col in client.list_collections():
        client.delete_collection(col.name)
    server._chroma_client = client
    server._current_collection = None
    yield
    server._chroma_client = None
    server._current_collection = None


@pytest.fixture
def tmp_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "UPLOADS_PATH", tmp_path)
    return tmp_path
