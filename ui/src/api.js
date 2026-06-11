async function _fetch(url, options) {
  const res = await fetch(url, options)
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

export function listNamespaces() {
  return _fetch('/namespaces')
}

export function currentNamespace() {
  return _fetch('/namespaces/current')
}

export function createNamespace(name) {
  return _fetch('/namespaces', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ name }) })
}

export function useNamespace(name) {
  return _fetch(`/namespaces/${encodeURIComponent(name)}/use`, { method: 'POST', headers: JSON_HEADERS })
}

export function deleteNamespace(name) {
  return _fetch(`/namespaces/${encodeURIComponent(name)}`, { method: 'DELETE', headers: JSON_HEADERS })
}

export function listIndexedPages() {
  return _fetch('/index/pages')
}

export function indexPage(url) {
  return _fetch('/index/page', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ url }) })
}

export function indexTree(url, maxDepth = 2, force = false) {
  return _fetch('/index/tree', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ url, max_depth: maxDepth, force }),
  })
}

export function searchDocs(query, nResults = 5) {
  const params = new URLSearchParams({ query, n_results: nResults })
  return _fetch(`/search?${params}`)
}

export function discoverLinks(url, maxDepth = 2) {
  const params = new URLSearchParams({ url, max_depth: maxDepth })
  return _fetch(`/links?${params}`)
}
