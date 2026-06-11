import { useState } from 'react'

const CONFIGS = {
  'search':     { hint: 'Search across all indexed content',          placeholder: 'Search the indexed docs…',        btn: 'Search',   hasDepth: false },
  'index-page': { hint: 'Index a single documentation page',          placeholder: 'https://docs.example.com/page',   btn: 'Index',    hasDepth: false },
  'index-tree': { hint: 'Recursively index a full documentation site', placeholder: 'https://docs.example.com/',      btn: 'Index',    hasDepth: true  },
  'discover':   { hint: 'Discover all reachable links on a domain',   placeholder: 'https://docs.example.com/',       btn: 'Discover', hasDepth: true  },
}

export default function InputArea({ tool, onSubmit, disabled }) {
  const [value, setValue] = useState('')
  const [depth, setDepth] = useState(2)
  const config = CONFIGS[tool]

  const handleSubmit = () => {
    const v = value.trim()
    if (!v) return
    onSubmit({ value: v, depth: config.hasDepth ? depth : null })
    setValue('')
  }

  return (
    <div className="px-4 py-3.5 border-b border-slate-800 shrink-0 bg-slate-950">
      <div className="text-[10px] text-slate-600 mb-1.5">{config.hint}</div>
      <div className="flex gap-2">
        <input
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !disabled && handleSubmit()}
          placeholder={config.placeholder}
          disabled={disabled}
          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3.5 py-2 text-slate-200 text-sm outline-none focus:border-sky-600 disabled:opacity-50"
        />
        <button
          onClick={handleSubmit}
          disabled={disabled}
          className="bg-sky-600 rounded-lg px-5 py-2 text-white text-sm disabled:opacity-50"
        >
          {config.btn}
        </button>
      </div>
      {config.hasDepth && (
        <div className="flex gap-4 mt-2 items-center">
          <label className="text-[11px] text-slate-500 flex items-center gap-1.5">
            Depth
            <input
              type="number"
              value={depth}
              min={1}
              max={10}
              disabled={disabled}
              onChange={e => setDepth(Number(e.target.value))}
              className="w-12 bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-slate-200 text-xs text-center"
            />
          </label>
        </div>
      )}
    </div>
  )
}
