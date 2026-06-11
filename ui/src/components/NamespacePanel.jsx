import { useState } from 'react'

export default function NamespacePanel({ namespaces, current, onCreate, onSwitch, onDelete }) {
  const [input, setInput] = useState('')

  const handleAdd = async () => {
    const name = input.trim()
    if (!name) return
    await onCreate(name)
    setInput('')
  }

  const others = namespaces.filter(ns => ns !== current)

  return (
    <div className="p-3.5 border-b border-slate-800">
      <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-2">Namespace</div>
      {current && (
        <div className="flex items-center gap-1.5 bg-slate-950 border border-sky-700 rounded-md px-2.5 py-1.5 mb-2.5">
          <span className="flex-1 text-sky-400 font-semibold text-sm">{current}</span>
          <button onClick={() => onDelete(current)} className="text-slate-500 hover:text-red-400 text-xs">✕</button>
        </div>
      )}
      <div className="flex flex-col gap-1 mb-2.5">
        {others.map(ns => (
          <div
            key={ns}
            onClick={() => onSwitch(ns)}
            className="flex items-center gap-1.5 bg-slate-950 rounded px-2.5 py-1.5 cursor-pointer hover:bg-slate-800"
          >
            <span className="flex-1 text-slate-400 text-xs">{ns}</span>
            <button
              onClick={e => { e.stopPropagation(); onDelete(ns) }}
              className="text-slate-700 hover:text-red-400 text-[11px]"
            >✕</button>
          </div>
        ))}
      </div>
      <div className="flex gap-1.5">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAdd()}
          placeholder="new namespace…"
          className="flex-1 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs outline-none focus:border-sky-600"
        />
        <button onClick={handleAdd} className="bg-sky-600 rounded px-2.5 py-1 text-white text-xs">Add</button>
      </div>
    </div>
  )
}
