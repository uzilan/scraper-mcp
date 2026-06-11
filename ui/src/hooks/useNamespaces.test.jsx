import { renderHook, act, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { useNamespaces } from './useNamespaces'
import * as api from '../api'

vi.mock('../api')

describe('useNamespaces', () => {
  beforeEach(() => {
    api.listNamespaces.mockResolvedValue(['ns1', 'ns2'])
    api.currentNamespace.mockResolvedValue('ns1')
  })

  it('loads namespaces and current namespace on mount', async () => {
    const { result } = renderHook(() => useNamespaces())
    await waitFor(() => expect(result.current.namespaces).toEqual(['ns1', 'ns2']))
    expect(result.current.current).toBe('ns1')
  })

  it('create calls api.createNamespace then refreshes', async () => {
    api.createNamespace.mockResolvedValue("Namespace 'new-ns' created and is now active.")
    api.listNamespaces
      .mockResolvedValueOnce(['ns1', 'ns2'])
      .mockResolvedValueOnce(['ns1', 'ns2', 'new-ns'])
    api.currentNamespace
      .mockResolvedValueOnce('ns1')
      .mockResolvedValueOnce('new-ns')

    const { result } = renderHook(() => useNamespaces())
    await waitFor(() => expect(result.current.namespaces).toHaveLength(2))

    await act(() => result.current.create('new-ns'))

    expect(api.createNamespace).toHaveBeenCalledWith('new-ns')
    await waitFor(() => expect(result.current.namespaces).toHaveLength(3))
    expect(result.current.current).toBe('new-ns')
  })

  it('switchTo calls api.useNamespace then refreshes', async () => {
    api.useNamespace.mockResolvedValue("Now using 'ns2'.")
    api.listNamespaces.mockResolvedValue(['ns1', 'ns2'])
    api.currentNamespace.mockResolvedValueOnce('ns1').mockResolvedValueOnce('ns2')

    const { result } = renderHook(() => useNamespaces())
    await waitFor(() => expect(result.current.current).toBe('ns1'))

    await act(() => result.current.switchTo('ns2'))

    expect(api.useNamespace).toHaveBeenCalledWith('ns2')
    await waitFor(() => expect(result.current.current).toBe('ns2'))
  })

  it('remove calls api.deleteNamespace then refreshes', async () => {
    api.deleteNamespace.mockResolvedValue("Namespace 'ns2' deleted.")
    api.listNamespaces.mockResolvedValueOnce(['ns1', 'ns2']).mockResolvedValueOnce(['ns1'])
    api.currentNamespace.mockResolvedValue('ns1')

    const { result } = renderHook(() => useNamespaces())
    await waitFor(() => expect(result.current.namespaces).toHaveLength(2))

    await act(() => result.current.remove('ns2'))

    expect(api.deleteNamespace).toHaveBeenCalledWith('ns2')
    await waitFor(() => expect(result.current.namespaces).toHaveLength(1))
  })
})
