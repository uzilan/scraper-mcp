import httpx
import pytest
import server
from router import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_create_namespace(client):
    response = await client.post("/namespaces", json={"name": "my-ns"})
    assert response.status_code == 200
    assert "my-ns" in response.json()


async def test_create_namespace_invalid_name(client):
    response = await client.post("/namespaces", json={"name": "x"})
    assert response.status_code == 400


async def test_list_namespaces_empty(client):
    response = await client.get("/namespaces")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_namespaces_after_create(client):
    await client.post("/namespaces", json={"name": "ns-a"})
    await client.post("/namespaces", json={"name": "ns-b"})
    response = await client.get("/namespaces")
    assert "ns-a" in response.json()
    assert "ns-b" in response.json()


async def test_delete_namespace(client):
    await client.post("/namespaces", json={"name": "to-delete"})
    response = await client.delete("/namespaces/to-delete")
    assert response.status_code == 200
    assert "deleted" in response.json().lower()


async def test_delete_namespace_not_found(client):
    response = await client.delete("/namespaces/ghost")
    assert response.status_code == 400


async def test_use_namespace(client):
    await client.post("/namespaces", json={"name": "switch-to"})
    # create a second namespace so current_namespace changes
    await client.post("/namespaces", json={"name": "other"})
    response = await client.post("/namespaces/switch-to/use")
    assert response.status_code == 200
    assert "switch-to" in response.json()


async def test_use_namespace_not_found(client):
    response = await client.post("/namespaces/ghost/use")
    assert response.status_code == 400


async def test_current_namespace_none(client):
    response = await client.get("/namespaces/current")
    assert response.status_code == 200
    assert "No namespace" in response.json()


async def test_current_namespace_set(client):
    await client.post("/namespaces", json={"name": "active"})
    response = await client.get("/namespaces/current")
    assert response.status_code == 200
    assert response.json() == "active"
