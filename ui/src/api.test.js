import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  listNamespaces, currentNamespace, createNamespace, useNamespace, deleteNamespace,
  listIndexedPages, indexPage, indexTree, searchDocs, discoverLinks,
} from './api'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockOk(data) {
  mockFetch.mockResolvedValueOnce({ ok: true, json: async () => data, text: async () => String(data) })
}
function mockError(status, text) {
  mockFetch.mockResolvedValueOnce({ ok: false, status, text: async () => text })
}

beforeEach(() => mockFetch.mockReset())

describe('listNamespaces', () => {
  it('GETs /namespaces and returns array', async () => {
    mockOk(['ns1', 'ns2'])
    expect(await listNamespaces()).toEqual(['ns1', 'ns2'])
    expect(mockFetch).toHaveBeenCalledWith('/namespaces', undefined)
  })
})

describe('currentNamespace', () => {
  it('GETs /namespaces/current and returns string', async () => {
    mockOk('ns1')
    expect(await currentNamespace()).toBe('ns1')
    expect(mockFetch).toHaveBeenCalledWith('/namespaces/current', undefined)
  })
})

describe('createNamespace', () => {
  it('POSTs name and returns message', async () => {
    mockOk("Namespace 'foo' created and is now active.")
    const result = await createNamespace('foo')
    expect(result).toContain('foo')
    expect(mockFetch).toHaveBeenCalledWith('/namespaces', expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'foo' }),
    }))
  })

  it('throws Error on non-OK response', async () => {
    mockError(400, 'Invalid name: must match [a-z0-9-]+')
    await expect(createNamespace('BAD')).rejects.toThrow('400: Invalid name')
  })
})

describe('useNamespace', () => {
  it('POSTs to /namespaces/{name}/use', async () => {
    mockOk("Now using 'ns2'.")
    await useNamespace('ns2')
    expect(mockFetch).toHaveBeenCalledWith('/namespaces/ns2/use', expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }))
  })
})

describe('deleteNamespace', () => {
  it('DELETEs /namespaces/{name}', async () => {
    mockOk("Namespace 'ns1' deleted.")
    await deleteNamespace('ns1')
    expect(mockFetch).toHaveBeenCalledWith('/namespaces/ns1', expect.objectContaining({
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    }))
  })
})

describe('listIndexedPages', () => {
  it('GETs /index/pages and returns page objects', async () => {
    mockOk([{ url: 'https://docs.example.com/page', chunks: 5 }])
    const result = await listIndexedPages()
    expect(result[0].url).toBe('https://docs.example.com/page')
    expect(result[0].chunks).toBe(5)
  })
})

describe('indexPage', () => {
  it('POSTs url to /index/page', async () => {
    mockOk('Indexed 7 chunks.')
    await indexPage('https://docs.example.com/page')
    expect(mockFetch).toHaveBeenCalledWith('/index/page', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ url: 'https://docs.example.com/page' }),
    }))
  })
})

describe('indexTree', () => {
  it('POSTs url + max_depth + force to /index/tree', async () => {
    mockOk('Indexed 12 pages.')
    await indexTree('https://docs.example.com/', 3, true)
    expect(mockFetch).toHaveBeenCalledWith('/index/tree', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ url: 'https://docs.example.com/', max_depth: 3, force: true }),
    }))
  })

  it('defaults max_depth=2 force=false', async () => {
    mockOk('Indexed 4 pages.')
    await indexTree('https://docs.example.com/')
    expect(mockFetch).toHaveBeenCalledWith('/index/tree', expect.objectContaining({
      body: JSON.stringify({ url: 'https://docs.example.com/', max_depth: 2, force: false }),
    }))
  })
})

describe('searchDocs', () => {
  it('GETs /search?query=...&n_results=5 and returns results dict', async () => {
    const payload = { results: [{ text: 'found it', url: 'https://docs.example.com/auth' }], references: [] }
    mockOk(payload)
    const result = await searchDocs('bearer token')
    expect(result.results[0].text).toBe('found it')
    expect(mockFetch).toHaveBeenCalledWith('/search?query=bearer+token&n_results=5', undefined)
  })
})

describe('discoverLinks', () => {
  it('GETs /links?url=...&max_depth=2 and returns string array', async () => {
    mockOk(['https://docs.example.com/page1', 'https://docs.example.com/page2'])
    const result = await discoverLinks('https://docs.example.com/', 2)
    expect(result).toHaveLength(2)
    expect(mockFetch).toHaveBeenCalledWith('/links?url=https%3A%2F%2Fdocs.example.com%2F&max_depth=2', undefined)
  })
})
