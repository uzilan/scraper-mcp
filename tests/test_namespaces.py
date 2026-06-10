import server
from server import chunk, parse


def test_create_namespace_valid():
    result = server._create_namespace(server._chroma_client, "my-ns")
    assert result == "Namespace 'my-ns' ready."


def test_create_namespace_idempotent():
    server._create_namespace(server._chroma_client, "my-ns")
    result = server._create_namespace(server._chroma_client, "my-ns")
    assert result == "Namespace 'my-ns' ready."


def test_create_namespace_invalid_name():
    result = server._create_namespace(server._chroma_client, "a")
    assert "Invalid name" in result


def test_list_namespaces_empty():
    assert server._list_namespaces(server._chroma_client) == []


def test_list_namespaces():
    server._create_namespace(server._chroma_client, "ns-one")
    server._create_namespace(server._chroma_client, "ns-two")
    names = server._list_namespaces(server._chroma_client)
    assert set(names) == {"ns-one", "ns-two"}


def test_use_namespace():
    server._create_namespace(server._chroma_client, "my-ns")
    result = server._use_namespace(server._chroma_client, "my-ns")
    assert result == "Using namespace 'my-ns'."
    assert server._current_collection is not None
    assert server._current_collection.name == "my-ns"


def test_use_namespace_nonexistent():
    result = server._use_namespace(server._chroma_client, "ghost")
    assert "does not exist" in result
    assert server._current_collection is None


def test_current_namespace_none():
    assert server._current_namespace() == "No namespace selected."


def test_current_namespace_set():
    server._create_namespace(server._chroma_client, "my-ns")
    server._use_namespace(server._chroma_client, "my-ns")
    assert server._current_namespace() == "my-ns"


def test_delete_namespace():
    server._create_namespace(server._chroma_client, "my-ns")
    result = server._delete_namespace(server._chroma_client, "my-ns")
    assert result == "Namespace 'my-ns' deleted."
    assert "my-ns" not in server._list_namespaces(server._chroma_client)


def test_delete_namespace_clears_current():
    server._create_namespace(server._chroma_client, "my-ns")
    server._use_namespace(server._chroma_client, "my-ns")
    server._delete_namespace(server._chroma_client, "my-ns")
    assert server._current_collection is None


def test_delete_namespace_nonexistent():
    result = server._delete_namespace(server._chroma_client, "ghost")
    assert "does not exist" in result


def test_chunk_splits_large_text():
    big = "\n\n".join(["word " * 100] * 10)
    result = chunk(big)
    assert len(result) > 1


def test_parse_strips_nav():
    html = "<html><body><nav>skip</nav><p>keep</p></body></html>"
    result = parse(html)
    assert "keep" in result
    assert "skip" not in result
