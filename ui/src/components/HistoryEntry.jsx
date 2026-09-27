import { useState, useRef, useEffect } from 'react'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const TOOL_CONFIG = {
  'ask':        { icon: '💬', label: 'Ask',           color: 'text-indigo-400' },
  'index-page': { icon: '📄', label: 'Index Page',    color: 'text-emerald-400' },
  'index-tree': { icon: '🌲', label: 'Index Tree',    color: 'text-orange-400' },
  'discover':   { icon: '🔗', label: 'Discover Links', color: 'text-pink-400'   },
}

function AskBody({ result }) {
  return (
    <div className="flex flex-col gap-2">
      <div
        className="prose prose-invert prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
        dangerouslySetInnerHTML={{ __html: marked(result.answer) }}
      />
      {result.references.length > 0 && (
        <div className="border-t border-slate-800 pt-2 flex flex-col gap-0.5">
          {result.references.map((url, i) => (
            <a key={i} href={url} target="_blank" rel="noreferrer" className="text-[10px] text-sky-400 no-underline">
              {url}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <div role="status" aria-label="Waiting for agent…" className="flex items-center gap-2 text-xs text-slate-500">
      <div className="w-3.5 h-3.5 border-2 border-slate-700 border-t-sky-500 rounded-full animate-spin" />
      Waiting for agent…
    </div>
  )
}

function LinkListBody({ links }) {
  return (
    <div className="flex flex-col gap-1">
      {links.map((url, i) => (
        <a key={i} href={url} target="_blank" rel="noreferrer" className="text-[11px] text-sky-400 no-underline">
          {url}
        </a>
      ))}
    </div>
  )
}

function UrlLog({ urls }) {
  const bottomRef = useRef(null)
  useEffect(() => {
    if (typeof bottomRef.current?.scrollIntoView === 'function') {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [urls])
  return (
    <div className="max-h-40 overflow-y-auto flex flex-col gap-0.5">
      {urls.map((msg, i) => (
        <span key={i} className={`text-[11px] ${msg.includes('[failed]') ? 'text-red-400' : 'text-slate-500'}`}>
          {msg}
        </span>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

function IndexTreeBody({ result, urls }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-slate-400 leading-relaxed">{result}</p>
      {urls.length > 0 && (
        <div className="border-t border-slate-800 pt-2">
          <UrlLog urls={urls} />
        </div>
      )}
    </div>
  )
}

export default function HistoryEntry({ entry, faded = false }) {
  const { tool, query, depth, result, error, urls = [], status = 'done' } = entry
  const tc = TOOL_CONFIG[tool] ?? { icon: '?', label: tool, color: 'text-slate-400' }
  const [collapsed, setCollapsed] = useState(faded)
  const isPending = status === 'pending'

  const summary = error ? 'error'
    : isPending ? '⋯'
    : tool === 'ask' ? '✓ answered'
    : tool === 'discover' ? `${result.length} links`
    : '✓ done'

  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-lg overflow-hidden${faded ? ' opacity-45' : ''}`}>
      <div
        onClick={() => faded && setCollapsed(c => !c)}
        className={`flex items-center gap-2 px-3.5 py-2 border-b border-slate-800 bg-slate-950${faded ? ' cursor-pointer hover:bg-slate-900' : ''}`}
      >
        <span className="text-sm">{tc.icon}</span>
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${tc.color}`}>{tc.label}</span>
        <span className="flex-1 text-[11px] text-slate-400 truncate">
          {query}{depth != null ? ` · depth ${depth}` : ''}
        </span>
        <span className="text-[10px] text-slate-600 whitespace-nowrap">{summary}</span>
        {faded && <span className="text-[10px] text-slate-700">{collapsed ? '▸' : '▾'}</span>}
      </div>
      {!collapsed && (
        <div className="px-3.5 py-2.5 flex flex-col gap-2">
          {error && <p className="text-xs text-red-400">{error}</p>}
          {!error && tool === 'ask' && (isPending ? <Spinner /> : <AskBody result={result} />)}
          {!error && tool === 'discover' && !isPending && <LinkListBody links={result} />}
          {!error && tool === 'index-tree' && !isPending && <IndexTreeBody result={result} urls={urls} />}
          {!error && tool === 'index-page' && (
            <p className="text-xs text-slate-400 leading-relaxed">{result}</p>
          )}
          {!error && isPending && tool !== 'ask' && <UrlLog urls={urls} />}
        </div>
      )}
    </div>
  )
}
