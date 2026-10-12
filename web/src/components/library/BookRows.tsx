// The list: one row a book, with the columns that fit the screen. Virtual,
// like the grid.
import { useEffect, useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import type { BookQuery } from '@/lib/api'
import { formatDate, seriesText } from '@/lib/format'
import { useBookList } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { Cover } from './Cover'
import { Stars } from './Stars'

interface Props {
  query: BookQuery
  selected: number | null
  onOpen: (id: number) => void
}

const ROW = 68
// Title, then series, rating and date added from the width where each fits.
const COLUMNS =
  'grid-cols-[40px_minmax(0,1fr)] md:grid-cols-[40px_minmax(0,2fr)_minmax(0,1fr)_88px] lg:grid-cols-[40px_minmax(0,2fr)_minmax(0,1fr)_88px_112px]'

export function BookRows({ query, selected, onOpen }: Props) {
  const scroller = useRef<HTMLDivElement>(null)
  const [range, setRange] = useState<[number, number]>([0, 0])
  const list = useBookList(query, range)
  const total = list.total ?? 0

  const virtualizer = useVirtualizer({
    count: total,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW,
    overscan: 8,
    paddingEnd: 32,
  })
  const items = virtualizer.getVirtualItems()
  const first = items[0]?.index ?? 0
  const last = items[items.length - 1]?.index ?? 0
  useEffect(() => {
    setRange((r) => (r[0] === first && r[1] === last ? r : [first, last]))
  }, [first, last])

  const key = JSON.stringify(query)
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 })
  }, [key])

  return (
    <div
      ref={scroller}
      className={cn(
        'min-h-0 flex-1 overflow-y-auto transition-opacity',
        list.stale && 'opacity-60',
      )}
    >
      <div
        className={cn(
          'sticky top-0 z-10 grid items-center gap-4 border-b bg-background/95 px-4 py-2 text-xs font-medium text-muted-foreground backdrop-blur sm:px-6',
          COLUMNS,
        )}
      >
        <span />
        <span>Title</span>
        <span className="hidden md:block">Series</span>
        <span className="hidden md:block">Rating</span>
        <span className="hidden lg:block">Added</span>
      </div>
      <div
        className="relative w-full"
        style={{ height: virtualizer.getTotalSize() }}
      >
        {items.map((v) => {
          const book = list.at(v.index)
          return (
            <div
              key={v.key}
              className="absolute inset-x-0"
              style={{ top: v.start, height: ROW }}
            >
              {book ? (
                <button
                  type="button"
                  onClick={() => onOpen(book.id)}
                  className={cn(
                    'grid h-full w-full items-center gap-4 border-b border-border/60 px-4 text-left text-sm outline-none hover:bg-accent/60 focus-visible:bg-accent sm:px-6',
                    COLUMNS,
                    selected === book.id && 'bg-accent',
                  )}
                >
                  <Cover library={query.library} book={book} width={40} />
                  <span className="min-w-0">
                    <span className="block truncate font-medium">
                      {book.title}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {book.authors?.join(', ')}
                    </span>
                  </span>
                  <span className="hidden truncate text-muted-foreground md:block">
                    {seriesText(book.series, book.series_index)}
                  </span>
                  <span className="hidden md:block">
                    <Stars rating={book.rating} />
                  </span>
                  <span className="hidden text-muted-foreground tabular-nums lg:block">
                    {formatDate(book.timestamp)}
                  </span>
                </button>
              ) : (
                <div
                  className={cn(
                    'grid h-full items-center gap-4 px-4 sm:px-6',
                    COLUMNS,
                  )}
                >
                  <div className="h-[60px] w-10 animate-pulse rounded-md bg-muted" />
                  <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
