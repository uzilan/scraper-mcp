import chromadb
import pytest
import namespaces


@pytest.fixture(autouse=True)
def default_agent_provider(monkeypatch):
    monkeypatch.delenv("AGENT_PROVIDER", raising=False)


@pytest.fixture(autouse=True)
def reset_state():
    client = chromadb.EphemeralClient()
    for col in client.list_collections():
        client.delete_collection(col.name)
    namespaces.chroma_client = client
    namespaces.current_collection = None
    yield
    namespaces.chroma_client = None
    namespaces.current_collection = None


@pytest.fixture
def tmp_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(namespaces, "UPLOADS_PATH", tmp_path)
    return tmp_path
