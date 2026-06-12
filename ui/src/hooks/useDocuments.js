import { useState, useEffect, useCallback } from 'react'
import { listDocuments } from '../api'

export function useDocuments(current) {
  const [documents, setDocuments] = useState([])

  const refresh = useCallback(async () => {
    if (!current) { setDocuments([]); return }
    try {
      const result = await listDocuments()
      setDocuments(result)
    } catch {
      setDocuments([])
    }
  }, [current])

  useEffect(() => { refresh() }, [refresh])

  return { documents, refresh }
}
