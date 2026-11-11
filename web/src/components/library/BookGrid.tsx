// The cover grid. Only the rows on screen exist, and only their pages of
// books are fetched, so a library of 10,000 scrolls like one of 100.
import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import type { BookQuery } from '@/lib/api'
import { useBookList } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { Cover, CoverPlaceholder } from './Cover'

interface Props {
  query: BookQuery
  selected: number | null
  onOpen: (id: number) => void
}

function useWidth(ref: RefObject<HTMLElement | null>) {
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width))
    ro.observe(el)
    setWidth(el.getBoundingClientRect().width)
    return () => ro.disconnect()
  }, [ref])
  return width
}

/** Columns and tile size for a width: as many tiles as fit at a comfortable size. */
export function gridGeometry(width: number) {
  const small = width < 560
  const gap = small ? 12 : 20
  const min = small ? 100 : 144
  const cols = Math.max(2, Math.floor((width + gap) / (min + gap)))
  const tile = Math.max(1, (width - gap * (cols - 1)) / cols)
  // The cover, a gap, two lines of title and one of authors.
  const row = Math.round(tile * 1.5 + 8 + 52 + gap)
  return { cols, tile, gap, row }
}

export function BookGrid({ query, selected, onOpen }: Props) {
  const scroller = useRef<HTMLDivElement>(null)
  const inner = useRef<HTMLDivElement>(null)
  const width = useWidth(inner)
  const { cols, tile, gap, row } = gridGeometry(width || 800)
  const [range, setRange] = useState<[number, number]>([0, 0])
  const list = useBookList(query, range)
  const total = list.total ?? 0
  const rows = Math.ceil(total / cols)

  const virtualizer = useVirtualizer({
    count: rows,
    getScrollElement: () => scroller.current,
    estimateSize: () => row,
    overscan: 3,
    paddingStart: 4,
    paddingEnd: 32,
  })
  useEffect(() => virtualizer.measure(), [row, virtualizer])

  const items = virtualizer.getVirtualItems()
  const firstRow = items[0]?.index ?? 0
  const lastRow = items[items.length - 1]?.index ?? 0
  useEffect(() => {
    setRange((r) => {
      const next: [number, number] = [firstRow * cols, (lastRow + 1) * cols - 1]
      return r[0] === next[0] && r[1] === next[1] ? r : next
    })
  }, [firstRow, lastRow, cols])

  // A new search starts at the top.
  const key = JSON.stringify(query)
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 })
  }, [key])

  return (
    <div
      ref={scroller}
      className={cn(
        'min-h-0 flex-1 overflow-y-auto px-4 transition-opacity sm:px-6',
        list.stale && 'opacity-60',
      )}
    >
      <div
        ref={inner}
        className="relative w-full"
        style={{ height: virtualizer.getTotalSize() }}
      >
        {items.map((v) => (
          <div
            key={v.key}
            className="absolute inset-x-0 grid"
            style={{
              top: v.start,
              gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
              columnGap: gap,
            }}
          >
            {Array.from({ length: cols }, (_, c) => {
              const index = v.index * cols + c
              if (index >= total) return <div key={c} />
              const book = list.at(index)
              if (!book) {
                return (
                  <div key={c}>
                    <CoverPlaceholder />
                  </div>
                )
              }
              return (
                <button
                  // Cells are keyed by column: a book id could equal a column
                  // number and confuse React into keeping a stale tile.
                  key={c}
                  type="button"
                  onClick={() => onOpen(book.id)}
                  className="group flex min-w-0 flex-col gap-2 rounded-lg text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  aria-label={`${book.title}${book.authors?.length ? ', by ' + book.authors.join(', ') : ''}`}
                >
                  <Cover
                    key={book.id}
                    library={query.library}
                    book={book}
                    width={tile}
                    className={cn(
                      'w-full shadow-sm transition-shadow group-hover:shadow-md',
                      selected === book.id && 'ring-2 ring-primary',
                    )}
                  />
                  <span className="min-w-0 px-0.5">
                    <span className="line-clamp-2 text-xs leading-snug font-medium sm:text-sm">
                      {book.title}
                    </span>
                    <span className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                      {book.authors?.join(', ')}
                    </span>
                  </span>
                </button>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
