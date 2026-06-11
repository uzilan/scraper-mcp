import { useState, useEffect, useCallback } from 'react'
import { listIndexedPages } from '../api'

export function usePages(current) {
  const [pages, setPages] = useState([])

  const refresh = useCallback(async () => {
    if (!current) { setPages([]); return }
    const result = await listIndexedPages()
    setPages(result)
  }, [current])

  useEffect(() => { refresh() }, [refresh])

  return { pages, refresh }
}
