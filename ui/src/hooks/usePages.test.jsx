import { renderHook, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { usePages } from './usePages'
import * as api from '../api'

vi.mock('../api')

describe('usePages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches pages when current namespace is set', async () => {
    api.listIndexedPages.mockResolvedValue([{ url: 'https://docs.example.com/page', chunks: 5 }])
    const { result } = renderHook(() => usePages('my-ns'))
    await waitFor(() => expect(result.current.pages).toHaveLength(1))
    expect(result.current.pages[0].url).toBe('https://docs.example.com/page')
  })

  it('returns empty pages when current is null', async () => {
    const { result } = renderHook(() => usePages(null))
    await waitFor(() => expect(result.current.pages).toEqual([]))
    expect(api.listIndexedPages).not.toHaveBeenCalled()
  })

  it('refetches when current namespace changes', async () => {
    api.listIndexedPages
      .mockResolvedValueOnce([{ url: 'https://docs.example.com/a', chunks: 2 }])
      .mockResolvedValueOnce([{ url: 'https://other.example.com/b', chunks: 3 }])

    const { result, rerender } = renderHook(({ ns }) => usePages(ns), { initialProps: { ns: 'ns1' } })
    await waitFor(() => expect(result.current.pages[0].url).toContain('docs.example'))

    rerender({ ns: 'ns2' })
    await waitFor(() => expect(result.current.pages[0].url).toContain('other.example'))
  })
})
