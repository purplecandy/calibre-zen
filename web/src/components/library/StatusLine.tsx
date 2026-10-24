// Under the top bar: how many books, and the filters in force as chips that
// each take themselves away.
import { IconX } from '@tabler/icons-react'
import type { LibraryInfo } from '@/lib/api'
import { books, formatCount } from '@/lib/format'
import { filterLabel, resetFor, setView, useView } from '@/lib/state'

export function StatusLine({
  info,
  total,
}: {
  info: LibraryInfo | undefined
  total: number | undefined
}) {
  const view = useView()
  const narrowed = !!(view.q || view.filters.length || view.vl)
  const fieldName = (expr: string) => {
    const key = expr.split(':', 1)[0]
    return info?.field_metadata[key]?.name ?? key
  }
  return (
    <div className="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-2 text-sm sm:px-6">
      <span className="text-muted-foreground tabular-nums" aria-live="polite">
        {total === undefined
          ? ''
          : narrowed && info
            ? `${formatCount(total)} of ${books(info.num_books)}`
            : books(total)}
      </span>
      {view.vl && (
        <Chip
          label={view.vl}
          title="Virtual library"
          onRemove={() => setView(resetFor({ vl: '' }))}
        />
      )}
      {view.filters.map((f) => (
        <Chip
          key={f}
          label={filterLabel(f)}
          title={fieldName(f)}
          onRemove={() =>
            setView(resetFor({ filters: view.filters.filter((x) => x !== f) }))
          }
        />
      ))}
      {(view.filters.length > 0 || view.vl || view.q) && (
        <button
          type="button"
          onClick={() => setView(resetFor({ filters: [], vl: '', q: '' }))}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Clear all
        </button>
      )}
    </div>
  )
}

function Chip({
  label,
  title,
  onRemove,
}: {
  label: string
  title: string
  onRemove: () => void
}) {
  return (
    <span className="inline-flex max-w-64 items-center gap-1 rounded-full border bg-card py-0.5 pr-1 pl-2.5 text-xs">
      <span className="text-muted-foreground">{title}:</span>
      <span className="truncate font-medium">{label}</span>
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${title}: ${label}`}
        className="rounded-full p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <IconX className="size-3" />
      </button>
    </span>
  )
}
