import { useState, useCallback } from 'react'
import NamespacePanel from './components/NamespacePanel'
import PagesList from './components/PagesList'
import ToolBar from './components/ToolBar'
import InputArea from './components/InputArea'
import History from './components/History'
import { useNamespaces } from './hooks/useNamespaces'
import { usePages } from './hooks/usePages'
import * as api from './api'

export default function App() {
  const { namespaces, current, create, switchTo, remove } = useNamespaces()
  const { pages, refresh: refreshPages } = usePages(current)
  const [tool, setTool] = useState('search')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)

  const handleSubmit = useCallback(async ({ value, depth }) => {
    setLoading(true)
    const entry = { id: Date.now(), tool, query: value, depth, result: null, error: null }
    try {
      if (tool === 'search') {
        entry.result = await api.searchDocs(value)
      } else if (tool === 'index-page') {
        entry.result = await api.indexPage(value)
        refreshPages()
      } else if (tool === 'index-tree') {
        entry.result = await api.indexTree(value, depth)
        refreshPages()
      } else if (tool === 'discover') {
        entry.result = await api.discoverLinks(value, depth)
      }
    } catch (e) {
      entry.error = e.message
    }
    setHistory(prev => [entry, ...prev])
    setLoading(false)
  }, [tool, refreshPages])

  return (
    <div className="bg-slate-950 text-slate-200 font-sans text-[13px] h-screen overflow-hidden flex">
      <div className="w-60 min-w-60 border-r border-slate-800 flex flex-col bg-slate-900">
        <NamespacePanel
          namespaces={namespaces}
          current={current}
          onCreate={create}
          onSwitch={switchTo}
          onDelete={remove}
        />
        <PagesList pages={pages} />
      </div>
      <div className="flex-1 flex flex-col overflow-hidden">
        <ToolBar active={tool} onChange={setTool} />
        <InputArea tool={tool} onSubmit={handleSubmit} disabled={loading} />
        <History entries={history} />
      </div>
    </div>
  )
}
