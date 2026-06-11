const TOOL_CONFIG = {
  'search':     { icon: '🔍', label: 'Search',        color: 'text-indigo-400' },
  'index-page': { icon: '📄', label: 'Index Page',    color: 'text-emerald-400' },
  'index-tree': { icon: '🌲', label: 'Index Tree',    color: 'text-orange-400' },
  'discover':   { icon: '🔗', label: 'Discover Links', color: 'text-pink-400'   },
}

function SearchBody({ result }) {
  return (
    <div className="flex flex-col gap-2">
      {result.results.map((r, i) => (
        <div key={i} className="border-l-2 border-blue-900 pl-2.5">
          <p className="text-xs text-slate-300 leading-relaxed mb-0.5">{r.text}</p>
          {r.url && (
            <a href={r.url} target="_blank" rel="noreferrer" className="text-[10px] text-sky-400 no-underline">
              {r.url}
            </a>
          )}
        </div>
      ))}
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

  const summary = error ? 'error'
    : tool === 'search' ? `${result.results.length} results`
    : tool === 'discover' ? `${result.length} links`
    : '✓ done'

  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-lg overflow-hidden${faded ? ' opacity-45' : ''}`}>
      <div className="flex items-center gap-2 px-3.5 py-2 border-b border-slate-800 bg-slate-950">
        <span className="text-sm">{tc.icon}</span>
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${tc.color}`}>{tc.label}</span>
        <span className="flex-1 text-[11px] text-slate-400 truncate">
          {query}{depth != null ? ` · depth ${depth}` : ''}
        </span>
        <span className="text-[10px] text-slate-600 whitespace-nowrap">{summary}</span>
      </div>
      <div className="px-3.5 py-2.5 flex flex-col gap-2">
        {error && <p className="text-xs text-red-400">{error}</p>}
        {!error && tool === 'search' && <SearchBody result={result} />}
        {!error && tool === 'discover' && <LinkListBody links={result} />}
        {!error && (tool === 'index-page' || tool === 'index-tree') && (
          <p className="text-xs text-slate-400 leading-relaxed">{result}</p>
        )}
      </div>
    </div>
  )
}
