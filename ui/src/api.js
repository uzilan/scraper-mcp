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

export function askAgent(query) {
  const params = new URLSearchParams({ query })
  return _fetch(`/ask?${params}`)
}

export function discoverLinks(url, maxDepth = 2) {
  const params = new URLSearchParams({ url, max_depth: maxDepth })
  return _fetch(`/links?${params}`)
}

export function indexTreeStream(url, maxDepth = 2, force = false, onEvent) {
  const params = new URLSearchParams({ url, max_depth: maxDepth, force })
  const es = new EventSource(`/index/tree/stream?${params}`)
  return new Promise((resolve, reject) => {
    es.onmessage = e => {
      const ev = JSON.parse(e.data)
      onEvent(ev)
      if (ev.type === 'done') { es.close(); resolve(ev.summary) }
    }
    es.onerror = () => { es.close(); reject(new Error('Stream error')) }
  })
}

export function discoverLinksStream(url, maxDepth = 2, onEvent) {
  const params = new URLSearchParams({ url, max_depth: maxDepth })
  const es = new EventSource(`/links/stream?${params}`)
  return new Promise((resolve, reject) => {
    es.onmessage = e => {
      const ev = JSON.parse(e.data)
      onEvent(ev)
      if (ev.type === 'done') { es.close(); resolve() }
    }
    es.onerror = () => { es.close(); reject(new Error('Stream error')) }
  })
}

export function uploadDocument(file) {
  const form = new FormData()
  form.append('file', file)
  return _fetch('/documents', { method: 'POST', body: form })
}

export function listDocuments() {
  return _fetch('/documents')
}

export function deleteDocument(name) {
  return _fetch(`/documents/${encodeURIComponent(name)}`, { method: 'DELETE', headers: JSON_HEADERS })
}

export function getDocumentUrl(name) {
  return `/documents/${encodeURIComponent(name)}`
}
