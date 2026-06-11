export default function PagesList({ pages }) {
  return (
    <div className="flex-1 overflow-hidden flex flex-col p-3.5">
      <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-2">
        Indexed Pages <span className="text-slate-700 ml-1">({pages.length})</span>
      </div>
      <div className="flex-1 overflow-y-auto flex flex-col gap-1">
        {pages.map((page) => (
          <a
            key={page.url}
            href={page.url}
            target="_blank"
            rel="noreferrer"
            title={page.url}
            className="text-sky-400 text-[11px] no-underline whitespace-nowrap overflow-hidden text-ellipsis block py-0.5 hover:text-sky-300"
          >
            {page.url}
          </a>
        ))}
      </div>
    </div>
  )
}
