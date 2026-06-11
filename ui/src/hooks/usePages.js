import { useState, useEffect, useCallback } from 'react'
import { listIndexedPages } from '../api'

export function usePages(current) {
  const [pages, setPages] = useState([])

  const refresh = useCallback(async () => {
    if (!current) { setPages([]); return }
    try {
      const result = await listIndexedPages()
      setPages(result)
    } catch {
      setPages([])
    }
  }, [current])

  useEffect(() => { refresh() }, [refresh])

  return { pages, refresh }
}
