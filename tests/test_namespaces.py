import namespaces
from parsing import chunk, parse


def test_create_namespace_valid():
    result = namespaces.create_namespace("my-ns")
    assert result == "Namespace 'my-ns' created and is now active."


def test_create_namespace_idempotent():
    namespaces.create_namespace("my-ns")
    result = namespaces.create_namespace("my-ns")
    assert result == "Namespace 'my-ns' created and is now active."


def test_create_namespace_invalid_name():
    result = namespaces.create_namespace("a")
    assert "Invalid name" in result


def test_list_namespaces_empty():
    assert namespaces.list_namespaces() == []


def test_list_namespaces():
    namespaces.create_namespace("ns-one")
    namespaces.create_namespace("ns-two")
    names = namespaces.list_namespaces()
    assert set(names) == {"ns-one", "ns-two"}


def test_use_namespace():
    namespaces.create_namespace("my-ns")
    result = namespaces.use_namespace("my-ns")
    assert result == "Using namespace 'my-ns'."
    assert namespaces.current_collection is not None
    assert namespaces.current_collection.name == "my-ns"


def test_use_namespace_nonexistent():
    result = namespaces.use_namespace("ghost")
    assert "does not exist" in result
    assert namespaces.current_collection is None


def test_current_namespace_none():
    assert namespaces.current_namespace() == "No namespace selected."


def test_current_namespace_set():
    namespaces.create_namespace("my-ns")
    namespaces.use_namespace("my-ns")
    assert namespaces.current_namespace() == "my-ns"


def test_delete_namespace():
    namespaces.create_namespace("my-ns")
    result = namespaces.delete_namespace("my-ns")
    assert result == "Namespace 'my-ns' deleted."
    assert "my-ns" not in namespaces.list_namespaces()


def test_delete_namespace_clears_current():
    namespaces.create_namespace("my-ns")
    namespaces.use_namespace("my-ns")
    namespaces.delete_namespace("my-ns")
    assert namespaces.current_collection is None


def test_delete_namespace_nonexistent():
    result = namespaces.delete_namespace("ghost")
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
