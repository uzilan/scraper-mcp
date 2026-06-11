import HistoryEntry from './HistoryEntry'

export default function History({ entries }) {
  return (
    <div className="flex-1 min-h-0 overflow-auto p-4 flex flex-col gap-3">
      {entries.map((entry, i) => (
        <HistoryEntry key={entry.id} entry={entry} faded={i > 0} />
      ))}
    </div>
  )
}
