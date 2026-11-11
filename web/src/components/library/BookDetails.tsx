// One book: its cover, what calibre knows about it, and its files. Opened
// over the list, so closing it puts you back where you were.
import { useMemo } from 'react'
import DOMPurify from 'dompurify'
import { IconDownload, IconExternalLink } from '@tabler/icons-react'
import type { Book, FieldMetadata, LibraryInfo } from '@/lib/api'
import { coverUrl, downloadUrl } from '@/lib/api'
import { formatDate, formatSize, formatYear, seriesText } from '@/lib/format'
import { useBook, useServerInfo } from '@/lib/queries'
import { preferredFormat } from '@/lib/reader'
import { fieldSearch, resetFor, setView } from '@/lib/state'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Cover } from './Cover'
import { ReadButton } from './ReadButton'
import { Stars } from './Stars'

interface Props {
  library: string
  info: LibraryInfo | undefined
  id: number
}

// Shown in the header, as files, or never: everything else in the book's
// fields is listed under Details, in the order calibre's own book details use.
const NOT_LISTED = new Set([
  'title',
  'authors',
  'series',
  'series_index',
  'rating',
  'comments',
  'formats',
  'id',
  'uuid',
  'path',
  'sort',
  'author_sort',
  'size',
  'last_modified',
  'cover',
  'marked',
  'ondevice',
  'in_tag_browser',
])

function filterBy(field: string, value: string) {
  setView(resetFor({ filters: [fieldSearch(field, value)], q: '', book: null }))
}

function Chip({
  field,
  value,
  label,
}: {
  field?: string
  value: string
  label?: string
}) {
  const cls =
    'inline-block max-w-full rounded-md bg-secondary px-2 py-0.5 text-left text-xs break-words text-secondary-foreground'
  if (!field) return <span className={cls}>{label ?? value}</span>
  return (
    <button
      type="button"
      onClick={() => filterBy(field, value)}
      className={cn(
        cls,
        'hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none',
      )}
      title={`Show books with ${label ?? value}`}
    >
      {label ?? value}
    </button>
  )
}

function sanitize(html: string): string {
  const clean = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
  const doc = new DOMParser().parseFromString(clean, 'text/html')
  doc.querySelectorAll('a[href]').forEach((a) => {
    a.setAttribute('target', '_blank')
    a.setAttribute('rel', 'noopener noreferrer')
  })
  return doc.body.innerHTML
}

/** One field's value, the way its kind of column reads best. */
function Value({
  field,
  fm,
  book,
}: {
  field: string
  fm: FieldMetadata
  book: Book
}) {
  const value = book[field]
  const clickable = !!fm.is_category
  switch (fm.datatype) {
    case 'rating':
      return <Stars rating={Number(value)} />
    case 'datetime':
      return (
        <>
          {field === 'pubdate'
            ? formatYear(String(value))
            : formatDate(String(value))}
        </>
      )
    case 'bool':
      return <>{value ? 'Yes' : 'No'}</>
    case 'series':
      return (
        <Chip
          field={clickable ? field : undefined}
          value={String(value)}
          label={seriesText(
            String(value),
            book[field + '_index'] as number | undefined,
          )}
        />
      )
    case 'comments':
      return (
        <div
          className="zen-prose text-sm"
          dangerouslySetInnerHTML={{ __html: sanitize(String(value)) }}
        />
      )
  }
  if (field === 'languages') {
    const names = book.lang_names ?? {}
    return (
      <div className="flex flex-wrap gap-1">
        {(value as string[]).map((code) => (
          <Chip
            key={code}
            field="languages"
            value={code}
            label={names[code] ?? code}
          />
        ))}
      </div>
    )
  }
  if (field === 'identifiers') {
    const links = book.urls_from_identifiers ?? []
    return (
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {links.map(([name, , , url]) => (
          <a
            key={url}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-link hover:underline"
          >
            {name}
            <IconExternalLink className="size-3" />
          </a>
        ))}
      </div>
    )
  }
  if (Array.isArray(value)) {
    return (
      <div className="flex flex-wrap gap-1">
        {value.map((v) => (
          <Chip
            key={String(v)}
            field={clickable ? field : undefined}
            value={String(v)}
          />
        ))}
      </div>
    )
  }
  if (clickable && typeof value === 'string')
    return <Chip field={field} value={value} />
  return <>{String(value)}</>
}

export function BookDetails({ library, info, id }: Props) {
  const book = useBook(library, id)
  const server = useServerInfo()

  const rows = useMemo(() => {
    const b = book.data
    if (!b || !info) return []
    const fm = info.field_metadata
    const order = [...info.book_display_fields]
    if (!order.includes('timestamp')) order.push('timestamp')
    return order.filter(
      (f) =>
        !NOT_LISTED.has(f) &&
        fm[f] &&
        b[f] !== undefined &&
        b[f] !== null &&
        b[f] !== '' &&
        !(Array.isArray(b[f]) && (b[f] as unknown[]).length === 0) &&
        // calibre counts pages as 0 until it has counted them.
        !(f === 'pages' && !b[f]),
    )
  }, [book.data, info])

  if (book.isPending) {
    return <p className="p-6 text-sm text-muted-foreground">Loading…</p>
  }
  if (book.isError || !book.data) {
    return (
      <p className="p-6 text-sm text-muted-foreground">
        This book could not be loaded.
      </p>
    )
  }
  const b = { ...book.data, id }
  const fm = info?.field_metadata ?? {}
  const readable = server.data && preferredFormat(b, server.data)

  return (
    <article className="flex flex-col gap-6 p-6">
      <div className="flex gap-5 sm:flex-col">
        <a
          href={coverUrl(library, b)}
          target="_blank"
          rel="noopener noreferrer"
          className="w-28 shrink-0 sm:w-44"
          aria-label="Open the cover at full size"
        >
          <Cover
            library={library}
            book={b}
            width={176}
            full
            eager
            className="w-full shadow-md"
          />
        </a>
        <header className="min-w-0">
          <h2 className="font-serif text-2xl leading-tight font-medium text-balance">
            {b.title}
          </h2>
          {b.authors && (
            <p className="mt-1.5 text-sm">
              {b.authors.map((a, i) => (
                <span key={a}>
                  {i > 0 && ', '}
                  <button
                    type="button"
                    className="hover:underline focus-visible:underline focus-visible:outline-none"
                    onClick={() => filterBy('authors', a)}
                  >
                    {a}
                  </button>
                </span>
              ))}
            </p>
          )}
          {b.series && (
            <p className="mt-1 text-sm text-muted-foreground">
              <button
                type="button"
                className="hover:underline"
                onClick={() => filterBy('series', b.series!)}
              >
                {seriesText(b.series, b.series_index)}
              </button>
            </p>
          )}
          {b.rating ? <Stars rating={b.rating} className="mt-2" /> : null}
        </header>
      </div>

      {b.formats && b.formats.length > 0 && (
        <section aria-label="Files" className="flex flex-wrap gap-2">
          <ReadButton library={library} book={b} />
          {b.formats.map((fmt, i) => (
            <Button
              key={fmt}
              asChild
              size="sm"
              variant={i === 0 && !readable ? 'default' : 'outline'}
            >
              <a href={downloadUrl(library, id, fmt)} download>
                <IconDownload />
                {fmt}
                <span className="font-normal opacity-70">
                  {formatSize(b.format_sizes?.[fmt])}
                </span>
              </a>
            </Button>
          ))}
        </section>
      )}

      {b.comments && (
        <section
          className="zen-prose text-sm leading-relaxed"
          dangerouslySetInnerHTML={{ __html: sanitize(b.comments) }}
        />
      )}

      {rows.length > 0 && (
        <section>
          <h3 className="mb-2 text-xs font-medium text-muted-foreground">
            Details
          </h3>
          <dl className="grid grid-cols-[minmax(0,7rem)_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-sm">
            {rows.map((f) => (
              <div key={f} className="contents">
                <dt className="truncate text-muted-foreground">
                  {f === 'timestamp' ? 'Added' : fm[f].name}
                </dt>
                <dd className="min-w-0">
                  <Value field={f} fm={fm[f]} book={b} />
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </article>
  )
}
