from unittest.mock import AsyncMock, patch

import httpx
import pytest

import openapi


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"openapi": "3.0.0", "paths": {}}, True),
        ({"swagger": "2.0", "paths": {}}, True),
        ({"paths": {}}, False),
        ({"openapi": "3.0.0"}, False),
    ],
)
def test_is_openapi_requires_version_and_paths(payload, expected):
    response = httpx.Response(200, json=payload)
    assert openapi.is_openapi(response) is expected


def test_is_openapi_rejects_invalid_json():
    response = httpx.Response(200, text="invalid", headers={"content-type": "application/json"})
    assert openapi.is_openapi(response) is False


def test_openapi_documents_resolves_request_and_response_schemas():
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Accounts API"},
        "components": {
            "schemas": {
                "Account": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"name": {"type": "string", "description": "Account name"}},
                }
            }
        },
        "paths": {
            "/accounts": {
                "parameters": [],
                "post": {
                    "operationId": "createAccount",
                    "summary": "Create account",
                    "requestBody": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Account"}}}
                    },
                    "responses": {
                        "201": {
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Account"}}}
                        }
                    },
                },
            }
        },
    }
    documents, document_ids, metadatas = openapi.openapi_documents(spec, "https://example.com/api.json")
    assert document_ids == ["https://example.com/api.json::createAccount"]
    assert metadatas == [{
        "source_url": "https://example.com/api.json",
        "path": "/accounts",
        "method": "post",
        "is_openapi": True,
    }]
    assert documents == [
        "# POST /accounts\n**API:** Accounts API\n**Summary:** Create account\n"
        "**Request Body:**\n- name* (string): Account name\n"
        "**Response:**\n- name* (string): Account name"
    ]


def test_recursive_schema_references_terminate():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "child": {"$ref": "#/components/schemas/Node"},
        },
    }
    spec = {
        "paths": {"/nodes": {"get": {
            "responses": {"200": {"content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/Node"}
            }}}}
        }}},
        "components": {"schemas": {"Node": schema}},
    }
    documents, document_ids, metadatas = openapi.openapi_documents(spec, "https://example.com/api.json")
    assert len(documents) == 1
    assert documents[0].count("- name (string)") == 1
    assert documents[0].count("- child (object)") == 1


async def test_swagger_initializer_resolves_relative_spec_url():
    response = httpx.Response(200, text='url: "/v3/api-docs"')
    with patch("crawling.fetch", new=AsyncMock(return_value=response)) as fetch:
        assert await openapi.resolve_swagger_spec_urls("https://example.com/swagger/index.html") == [
            "https://example.com/v3/api-docs"
        ]
    fetch.assert_awaited_once_with("https://example.com/swagger/swagger-initializer.js")


async def test_swagger_index_config_fallback_resolves_all_specs():
    response = httpx.Response(200, text='JSON.parse(\'{"urls": [{"url": "/api/a"}, {"url": "/api/b"}]}\')')
    with patch("crawling.fetch", new=AsyncMock(side_effect=[None, response])):
        assert await openapi.resolve_swagger_spec_urls("https://example.com/swagger/index.html") == [
            "https://example.com/api/a", "https://example.com/api/b"
        ]
