import { useState, useCallback, useRef } from 'react'
import NamespacePanel from './components/NamespacePanel'
import PagesList from './components/PagesList'
import DocumentsList from './components/DocumentsList'
import ToolBar from './components/ToolBar'
import InputArea from './components/InputArea'
import History from './components/History'
import { useNamespaces } from './hooks/useNamespaces'
import { usePages } from './hooks/usePages'
import { useDocuments } from './hooks/useDocuments'
import * as api from './api'

export default function App() {
  const { namespaces, current, create, switchTo, remove } = useNamespaces()
  const { pages, refresh: refreshPages } = usePages(current)
  const { documents, refresh: refreshDocuments } = useDocuments(current)
  const [tool, setTool] = useState('ask')
  const [history, setHistory] = useState([])
  const [status, setStatus] = useState('idle')
  const [sidebarWidth, setSidebarWidth] = useState(300)
  const sidebarRef = useRef(null)
  const statusTimer = useRef(null)

  const setDone = useCallback(() => {
    setStatus('done')
    clearTimeout(statusTimer.current)
    statusTimer.current = setTimeout(() => setStatus('idle'), 1500)
  }, [])

  const handleDividerMouseDown = (e) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = sidebarRef.current.offsetWidth
    const onMouseMove = (e) => {
      setSidebarWidth(Math.max(160, Math.min(800, startWidth + e.clientX - startX)))
    }
    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }

  const handleSubmit = useCallback(async ({ value, depth }) => {
    setStatus('loading')
    const entry = { id: Date.now(), tool, query: value, depth, result: null, error: null, urls: [], status: 'done' }

    if (tool === 'index-tree' || tool === 'discover') {
      entry.status = 'pending'
      setHistory(prev => [entry, ...prev])
      const collected = []
      const onEvent = (ev) => {
        if (ev.type === 'progress') {
          collected.push(ev.message)
          setHistory(prev => prev.map(e =>
            e.id === entry.id ? { ...e, urls: [...collected] } : e
          ))
        }
      }
      try {
        if (tool === 'index-tree') {
          const summary = await api.indexTreeStream(value, depth, false, onEvent)
          setHistory(prev => prev.map(e =>
            e.id === entry.id ? { ...e, result: summary, status: 'done' } : e
          ))
          refreshPages()
        } else {
          await api.discoverLinksStream(value, depth, onEvent)
          setHistory(prev => prev.map(e =>
            e.id === entry.id ? { ...e, result: [...collected], status: 'done' } : e
          ))
        }
      } catch (err) {
        setHistory(prev => prev.map(e =>
          e.id === entry.id ? { ...e, error: err.message, status: 'done' } : e
        ))
      }
      setDone()
      return
    }

    if (tool === 'ask') {
      entry.namespace = current
      entry.status = 'pending'
      setHistory(prev => [entry, ...prev])
      try {
        const result = await api.askAgent(value)
        setHistory(prev => prev.map(e =>
          e.id === entry.id ? { ...e, result, status: 'done' } : e
        ))
      } catch (err) {
        setHistory(prev => prev.map(e =>
          e.id === entry.id ? { ...e, error: err.message, status: 'done' } : e
        ))
      }
      setDone()
      return
    }

    try {
      if (tool === 'index-page') {
        entry.result = await api.indexPage(value)
        refreshPages()
      }
    } catch (e) {
      entry.error = e.message
    }
    setHistory(prev => [entry, ...prev])
    setDone()
  }, [tool, current, refreshPages, setDone])

  return (
    <div className="bg-slate-950 text-slate-200 font-sans text-[13px] h-screen overflow-hidden flex">
      <div ref={sidebarRef} style={{ width: sidebarWidth }} className="shrink-0 flex flex-col bg-slate-900 h-screen overflow-hidden">
        <NamespacePanel
          namespaces={namespaces}
          current={current}
          onCreate={create}
          onSwitch={switchTo}
          onDelete={remove}
        />
        <DocumentsList
          documents={documents}
          onUpload={async (file) => {
            try {
              await api.uploadDocument(file)
              refreshDocuments()
            } catch (e) {
              return { ok: false, error: e.message }
            }
          }}
          onDelete={async (name) => {
            try {
              await api.deleteDocument(name)
              refreshDocuments()
            } catch {
              // silent
            }
          }}
        />
        <PagesList pages={pages} />
      </div>
      <div
        onMouseDown={handleDividerMouseDown}
        className="w-1 shrink-0 bg-slate-800 hover:bg-sky-600 cursor-col-resize transition-colors"
      />
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <ToolBar active={tool} onChange={setTool} />
        <InputArea tool={tool} onSubmit={handleSubmit} status={status} />
        <History entries={history} />
      </div>
    </div>
  )
}
