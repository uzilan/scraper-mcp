import { useState, useEffect, useCallback } from 'react'
import { listNamespaces, currentNamespace, createNamespace, useNamespace, deleteNamespace } from '../api'

export function useNamespaces() {
  const [namespaces, setNamespaces] = useState([])
  const [current, setCurrent] = useState(null)

  const refresh = useCallback(async () => {
    const [all, curr] = await Promise.all([listNamespaces(), currentNamespace()])
    setNamespaces(all)
    setCurrent(curr)
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const create = useCallback(async (name) => {
    await createNamespace(name)
    await refresh()
  }, [refresh])

  const switchTo = useCallback(async (name) => {
    await useNamespace(name)
    await refresh()
  }, [refresh])

  const remove = useCallback(async (name) => {
    await deleteNamespace(name)
    await refresh()
  }, [refresh])

  return { namespaces, current, create, switchTo, remove, refresh }
}
