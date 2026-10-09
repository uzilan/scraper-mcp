import json
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

import crawling


def is_openapi(response: httpx.Response) -> bool:
    ct = response.headers.get("content-type", "")
    if "json" not in ct:
        return False
    try:
        spec = response.json()
        return "paths" in spec and ("openapi" in spec or "swagger" in spec)
    except Exception:
        return False


async def resolve_swagger_spec_urls(swagger_ui_url: str) -> list[str]:
    base = swagger_ui_url.rsplit("/", 1)[0]
    parsed = urlparse(swagger_ui_url)
    api_base = f"{parsed.scheme}://{parsed.netloc}"

    response = await crawling.fetch(f"{base}/swagger-initializer.js")
    if response:
        match = re.search(r'url:\s*["\']([^"\']+)["\']', response.text)
        if match:
            spec_url = urljoin(api_base, match.group(1))
            if "petstore" not in spec_url:
                return [spec_url]

    response = await crawling.fetch(f"{base}/index.js")
    if response:
        match = re.search(r"JSON\.parse\('(.+?)'\)", response.text)
        if match:
            try:
                config = json.loads(match.group(1))
                urls = config.get("urls", [])
                return [urljoin(api_base, u["url"]) for u in urls if "url" in u]
            except Exception:
                pass

    return []


def extract_swagger_ui_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = []
    for tag in soup.find_all("a", href=True):
        url = urljoin(base_url, tag["href"]).split("#")[0]
        if re.search(r"/swagger/index\.html$", url):
            links.append(url)
    return list(dict.fromkeys(links))


def openapi_documents(spec: dict, url: str) -> tuple[list[str], list[str], list[dict]]:
    info = spec.get("info", {})
    base_title = info.get("title", "")
    components = spec.get("components", {})
    documents, ids, metadatas = [], [], []
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = operation.get("operationId", f"{method}_{path}")
            summary = operation.get("summary", "")
            description = operation.get("description", "")
            tags = ", ".join(operation.get("tags", []))
            params = [
                f"- {p.get('name')} ({p.get('in')}): {p.get('description', '')}"
                for p in operation.get("parameters", [])
            ]
            params_text = "\n".join(params) if params else ""

            request_body = operation.get("requestBody", {})
            request_text = extract_schema_text(request_body.get("content", {}), components)

            response_text = ""
            for code, response in operation.get("responses", {}).items():
                if str(code).startswith("2"):
                    response_text = extract_schema_text(response.get("content", {}), components)
                    break

            text = "\n".join(filter(None, [
                f"# {method.upper()} {path}",
                f"**API:** {base_title}",
                f"**Tags:** {tags}" if tags else None,
                f"**Summary:** {summary}" if summary else None,
                description if description else None,
                f"**Parameters:**\n{params_text}" if params_text else None,
                f"**Request Body:**\n{request_text}" if request_text else None,
                f"**Response:**\n{response_text}" if response_text else None,
            ]))
            documents.append(text)
            ids.append(f"{url}::{op_id}")
            metadatas.append({"source_url": url, "path": path, "method": method, "is_openapi": True})
    return documents, ids, metadatas


def resolve_ref(schema: dict, components: dict) -> dict:
    ref = schema.get("$ref", "")
    if not ref.startswith("#/components/schemas/"):
        return schema
    name = ref.split("/")[-1]
    return components.get("schemas", {}).get(name, schema)


def schema_to_text(schema: dict, components: dict, depth: int = 0, visited: frozenset = frozenset()) -> str:
    if depth > 4:
        return ""
    schema = resolve_ref(schema, components)
    ref_key = schema.get("$ref", id(schema))
    if ref_key in visited:
        return ""
    visited = visited | {ref_key}

    lines = []
    indent = "  " * depth

    for sub in schema.get("allOf", []) + schema.get("anyOf", []) + schema.get("oneOf", []):
        lines.append(schema_to_text(resolve_ref(sub, components), components, depth, visited))

    if "properties" in schema or schema.get("type") == "object":
        required_fields = set(schema.get("required", []))
        for name, prop in schema.get("properties", {}).items():
            prop = resolve_ref(prop, components)
            prop_type = prop.get("type", "object" if "properties" in prop else "")
            if prop_type == "array" and "items" in prop:
                prop_type = f"array[{resolve_ref(prop['items'], components).get('type', 'object')}]"
            req = "*" if name in required_fields else ""
            desc = prop.get("description", "")
            line = f"{indent}- {name}{req} ({prop_type})"
            if desc:
                line += f": {desc}"
            lines.append(line)
            if "properties" in prop or "allOf" in prop or "anyOf" in prop or "oneOf" in prop:
                lines.append(schema_to_text(prop, components, depth + 1, visited))
    elif schema.get("type") == "array" and "items" in schema:
        lines.append(schema_to_text(resolve_ref(schema["items"], components), components, depth, visited))

    return "\n".join(filter(None, lines))


def extract_schema_text(content: dict, components: dict) -> str:
    for media_content in content.values():
        schema = media_content.get("schema", {})
        if schema:
            return schema_to_text(schema, components)
    return ""
