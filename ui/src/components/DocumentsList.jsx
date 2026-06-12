import { useRef, useState } from 'react'
import { getDocumentUrl } from '../api'

const OPEN_IN_BROWSER = new Set(['.pdf', '.txt', '.md', '.json', '.yaml', '.yml'])

function getExt(name) {
  const idx = name.lastIndexOf('.')
  return idx >= 0 ? name.slice(idx).toLowerCase() : ''
}

function fileIcon(name) {
  const ext = getExt(name)
  if (ext === '.pdf') return '📄'
  if (ext === '.docx') return '📝'
  if (ext === '.xlsx') return '📊'
  if (ext === '.json' || ext === '.yaml' || ext === '.yml') return '⚙️'
  return '📃'
}

export default function DocumentsList({ documents, onUpload, onDelete }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const handleFiles = (files) => {
    for (const file of files) onUpload(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFiles([...e.dataTransfer.files])
  }

  return (
    <div
      className={`flex flex-col p-3.5 border-b border-slate-800${dragging ? ' bg-slate-800' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="text-[10px] uppercase tracking-widest text-slate-600">
          Documents <span className="text-slate-700 ml-1">({documents.length})</span>
        </div>
        <button
          onClick={() => inputRef.current?.click()}
          className="text-[10px] text-slate-500 hover:text-sky-400 px-1 leading-none"
          title="Upload document"
        >
          +
        </button>
      </div>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".pdf,.docx,.xlsx,.json,.yaml,.yml,.txt,.md"
        multiple
        onChange={(e) => handleFiles([...e.target.files])}
      />
      <div className="flex flex-col gap-0.5">
        {documents.map((doc) => {
          const ext = getExt(doc.name)
          const url = getDocumentUrl(doc.name)
          const openInBrowser = OPEN_IN_BROWSER.has(ext)
          return (
            <div key={doc.name} className="flex items-center gap-1 group">
              {openInBrowser ? (
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  title={doc.name}
                  className="text-sky-400 text-[11px] no-underline truncate flex-1 hover:text-sky-300"
                >
                  {fileIcon(doc.name)} {doc.name}
                </a>
              ) : (
                <a
                  href={url}
                  download
                  title={doc.name}
                  className="text-sky-400 text-[11px] no-underline truncate flex-1 hover:text-sky-300"
                >
                  {fileIcon(doc.name)} {doc.name}
                </a>
              )}
              <button
                onClick={() => onDelete(doc.name)}
                aria-label={`Delete ${doc.name}`}
                className="text-slate-700 hover:text-red-400 text-[10px] opacity-0 group-hover:opacity-100"
              >
                ×
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
