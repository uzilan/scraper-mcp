import { useState, useEffect, useCallback } from 'react'
import { listNamespaces, currentNamespace, createNamespace, useNamespace, deleteNamespace } from '../api'

export function useNamespaces() {
  const [namespaces, setNamespaces] = useState([])
  const [current, setCurrent] = useState(null)
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [all, curr] = await Promise.all([listNamespaces(), currentNamespace()])
      setNamespaces(all)
      setCurrent(curr)
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const create = useCallback(async (name) => {
    try {
      await createNamespace(name)
      await refresh()
    } catch (e) {
      setError(e.message)
    }
  }, [refresh])

  const switchTo = useCallback(async (name) => {
    try {
      await useNamespace(name)
      await refresh()
    } catch (e) {
      setError(e.message)
    }
  }, [refresh])

  const remove = useCallback(async (name) => {
    try {
      await deleteNamespace(name)
      await refresh()
    } catch (e) {
      setError(e.message)
    }
  }, [refresh])

  return { namespaces, current, error, create, switchTo, remove, refresh }
}
