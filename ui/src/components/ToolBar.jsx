const TOOLS = [
  { id: 'search', label: 'Search', icon: '🔍' },
  { id: 'index-page', label: 'Index Page', icon: '📄' },
  { id: 'index-tree', label: 'Index Tree', icon: '🌲' },
  { id: 'discover', label: 'Discover Links', icon: '🔗' },
]

export default function ToolBar({ active, onChange }) {
  return (
    <div className="px-4 py-3 border-b border-slate-800 flex gap-5 items-center bg-slate-900 shrink-0">
      {TOOLS.map(t => (
        <label
          key={t.id}
          className={`flex items-center gap-1.5 cursor-pointer text-sm ${active === t.id ? 'text-sky-400' : 'text-slate-400'}`}
        >
          <input
            type="radio"
            name="tool"
            aria-label={t.label}
            checked={active === t.id}
            onChange={() => onChange(t.id)}
            className="accent-sky-600"
          />
          {t.icon} {t.label}
        </label>
      ))}
    </div>
  )
}
