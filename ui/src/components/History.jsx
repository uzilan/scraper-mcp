import HistoryEntry from './HistoryEntry'

export default function History({ entries }) {
  const latestAnsweredAsk = entries.findIndex(entry =>
    entry.tool === 'ask' && entry.status !== 'pending' && !entry.error && entry.result
  )

  return (
    <div className="flex-1 min-h-0 overflow-auto p-4 flex flex-col gap-3">
      {entries.map((entry, i) => (
        <HistoryEntry
          key={entry.id}
          entry={entry}
          faded={i > 0}
          autoCollapse={entry.tool === 'ask' && latestAnsweredAsk !== -1 && i > latestAnsweredAsk}
        />
      ))}
    </div>
  )
}
