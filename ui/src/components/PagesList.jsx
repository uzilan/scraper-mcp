import { useState } from 'react'

function buildTree(pages) {
  const roots = new Map()
  for (const page of pages) {
    try {
      const { host, pathname } = new URL(page.url)
      const segments = pathname.split('/').filter(Boolean)
      if (!roots.has(host)) roots.set(host, { children: new Map(), pages: [] })
      let node = roots.get(host)
      for (let i = 0; i < segments.length - 1; i++) {
        const seg = segments[i]
        if (!node.children.has(seg)) node.children.set(seg, { children: new Map(), pages: [] })
        node = node.children.get(seg)
      }
      const label = segments[segments.length - 1] || host
      node.pages.push({ url: page.url, label })
    } catch {
      // skip unparseable URLs
    }
  }
  return roots
}

function FolderNode({ seg, node }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1 text-slate-500 text-[11px] py-0.5 w-full text-left hover:text-slate-400"
      >
        <span className="w-2 shrink-0">{open ? '▾' : '▸'}</span>
        {seg}/
      </button>
      {open && <TreeChildren node={node} />}
    </div>
  )
}

function TreeChildren({ node }) {
  return (
    <div style={{ paddingLeft: 10, borderLeft: '1px solid #1e293b', marginLeft: 2 }}>
      {[...node.children.entries()].map(([seg, child]) => (
        <FolderNode key={seg} seg={seg} node={child} />
      ))}
      {node.pages.map((page) => (
        <a
          key={page.url}
          href={page.url}
          target="_blank"
          rel="noreferrer"
          title={page.url}
          className="text-sky-400 text-[11px] no-underline whitespace-nowrap block py-0.5 hover:text-sky-300"
        >
          {page.label}
        </a>
      ))}
    </div>
  )
}

function DomainNode({ host, node }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1 text-slate-400 text-[11px] font-medium py-0.5 mt-1 w-full text-left hover:text-slate-300"
      >
        <span className="w-2 shrink-0">{open ? '▾' : '▸'}</span>
        {host}
      </button>
      {open && <TreeChildren node={node} />}
    </div>
  )
}

export default function PagesList({ pages }) {
  const tree = buildTree(pages)
  return (
    <div className="flex-1 min-h-0 overflow-hidden flex flex-col p-3.5">
      <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-2">
        Indexed Pages <span className="text-slate-700 ml-1">({pages.length})</span>
      </div>
      <div className="flex-1 min-h-0 overflow-auto flex flex-col gap-1">
        {[...tree.entries()].map(([host, node]) => (
          <DomainNode key={host} host={host} node={node} />
        ))}
      </div>
    </div>
  )
}
