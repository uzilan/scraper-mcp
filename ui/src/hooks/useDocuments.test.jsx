import { renderHook, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { useDocuments } from './useDocuments'
import * as api from '../api'

vi.mock('../api')

describe('useDocuments', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches documents when current namespace is set', async () => {
    api.listDocuments.mockResolvedValue([{ name: 'guide.pdf', size: 1024, content_type: 'application/pdf' }])
    const { result } = renderHook(() => useDocuments('my-ns'))
    await waitFor(() => expect(result.current.documents).toHaveLength(1))
    expect(result.current.documents[0].name).toBe('guide.pdf')
  })

  it('returns empty documents when current is null', async () => {
    const { result } = renderHook(() => useDocuments(null))
    await waitFor(() => expect(result.current.documents).toEqual([]))
    expect(api.listDocuments).not.toHaveBeenCalled()
  })

  it('refetches when current namespace changes', async () => {
    api.listDocuments
      .mockResolvedValueOnce([{ name: 'a.pdf', size: 100, content_type: 'application/pdf' }])
      .mockResolvedValueOnce([{ name: 'b.txt', size: 200, content_type: 'text/plain' }])

    const { result, rerender } = renderHook(({ ns }) => useDocuments(ns), { initialProps: { ns: 'ns1' } })
    await waitFor(() => expect(result.current.documents[0].name).toBe('a.pdf'))

    rerender({ ns: 'ns2' })
    await waitFor(() => expect(result.current.documents[0].name).toBe('b.txt'))
  })

  it('exposes a refresh function', async () => {
    api.listDocuments.mockResolvedValue([])
    const { result } = renderHook(() => useDocuments('my-ns'))
    await waitFor(() => expect(result.current.documents).toEqual([]))
    expect(typeof result.current.refresh).toBe('function')
  })
})
