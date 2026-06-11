import { useState } from 'react'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const TOOL_CONFIG = {
  'search':     { icon: '🔍', label: 'Search',        color: 'text-indigo-400' },
  'index-page': { icon: '📄', label: 'Index Page',    color: 'text-emerald-400' },
  'index-tree': { icon: '🌲', label: 'Index Tree',    color: 'text-orange-400' },
  'discover':   { icon: '🔗', label: 'Discover Links', color: 'text-pink-400'   },
}

function SearchResult({ r }) {
  const [expanded, setExpanded] = useState(false)
  const long = r.text.length > 300
  return (
    <div className="border-l-2 border-blue-900 pl-2.5">
      <div
        className={`prose prose-invert prose-sm max-w-none mb-0.5 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0${expanded ? ' max-h-64 overflow-y-auto' : ''}`}
        dangerouslySetInnerHTML={{ __html: marked(long && !expanded ? r.text.slice(0, 300) + '…' : r.text) }}
      />
      {long && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-[10px] text-slate-500 hover:text-slate-300 mb-0.5"
        >
          {expanded ? 'show less' : 'show more'}
        </button>
      )}
      {r.source_url && (
        <a href={r.source_url} target="_blank" rel="noreferrer" className="text-[10px] text-sky-400 no-underline block">
          {r.source_url}
        </a>
      )}
    </div>
  )
}

function SearchBody({ result }) {
  return (
    <div className="flex flex-col gap-2">
      {result.results.map((r, i) => <SearchResult key={i} r={r} />)}
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

export default function HistoryEntry({ entry, faded = false }) {
  const { tool, query, depth, result, error } = entry
  const tc = TOOL_CONFIG[tool] ?? { icon: '?', label: tool, color: 'text-slate-400' }
  const [collapsed, setCollapsed] = useState(faded)

  const summary = error ? 'error'
    : tool === 'search' ? `${result.results.length} results`
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
          {!error && tool === 'search' && <SearchBody result={result} />}
          {!error && tool === 'discover' && <LinkListBody links={result} />}
          {!error && (tool === 'index-page' || tool === 'index-tree') && (
            <p className="text-xs text-slate-400 leading-relaxed">{result}</p>
          )}
        </div>
      )}
    </div>
  )
}
