// Where to look: the library, its virtual libraries, and filters by author,
// tag, series and every other field calibre can browse by. The same list the
// desktop's filter panel shows, one level at a time.
import { useMemo, useState, type ReactNode } from 'react'
import {
  IconBooks,
  IconCheck,
  IconChevronRight,
  IconFileSearch,
  IconFilter,
  IconLibrary,
} from '@tabler/icons-react'
import type { BrowseField, LibraryInfo } from '@/lib/api'
import { app } from '@/lib/base'
import { formatCount } from '@/lib/format'
import { useBrowseField, useServerInfo } from '@/lib/queries'
import { resetFor, setView, useView } from '@/lib/state'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'

interface Props {
  library: string
  info: LibraryInfo | undefined
  onNavigate?: () => void
}

function Row({
  active,
  onClick,
  children,
  count,
  icon,
}: {
  active?: boolean
  onClick: () => void
  children: ReactNode
  count?: number
  icon?: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active || undefined}
      className={cn(
        'flex w-full min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-sidebar-foreground/90 outline-none hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-sidebar-ring',
        active && 'bg-sidebar-accent font-medium text-sidebar-foreground',
      )}
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {count !== undefined && (
        <span className="text-xs text-muted-foreground tabular-nums">
          {formatCount(count)}
        </span>
      )}
    </button>
  )
}

function Heading({ children }: { children: ReactNode }) {
  return (
    <h2 className="px-2 pt-5 pb-1 text-xs font-medium text-muted-foreground">
      {children}
    </h2>
  )
}

export function Sidebar({ library, info, onNavigate }: Props) {
  const view = useView()
  const server = useServerInfo()
  const libraries = Object.entries(server.data?.library_map ?? {})
  const vls = Object.keys(info?.virtual_libraries ?? {}).sort((a, b) =>
    a.localeCompare(b),
  )
  const fields = (info?.browse_fields ?? []).filter((f) => f.default_visible)

  const go = (change: Parameters<typeof setView>[0]) => {
    setView(resetFor(change))
    onNavigate?.()
  }

  return (
    <nav aria-label="Library" className="flex flex-col px-3 pb-6">
      {libraries.length > 1 && (
        <>
          <Heading>Libraries</Heading>
          {libraries.map(([id, name]) => (
            <Row
              key={id}
              active={id === library}
              onClick={() => go({ library: id, vl: '', filters: [], q: '' })}
              icon={<IconLibrary className="size-4 shrink-0 opacity-70" />}
            >
              {name}
            </Row>
          ))}
        </>
      )}

      <Heading>Books</Heading>
      <Row
        active={!view.vl && view.filters.length === 0}
        onClick={() => go({ vl: '', filters: [] })}
        count={info?.num_books}
        icon={<IconBooks className="size-4 shrink-0 opacity-70" />}
      >
        All books
      </Row>
      {vls.map((name) => (
        <Row
          key={name}
          active={view.vl === name}
          onClick={() => go({ vl: name })}
        >
          <span className="pl-6">{name}</span>
        </Row>
      ))}
      <Row
        onClick={() =>
          location.assign(app(`search/?library=${encodeURIComponent(library)}`))
        }
        icon={<IconFileSearch className="size-4 shrink-0 opacity-70" />}
      >
        Search book text
      </Row>

      {fields.length > 0 && <Heading>Filters</Heading>}
      {fields.map((field) => (
        <FieldFilter
          key={field.key}
          library={library}
          field={field}
          onNavigate={onNavigate}
        />
      ))}
    </nav>
  )
}

const SHOWN = 30

function FieldFilter({
  library,
  field,
  onNavigate,
}: {
  library: string
  field: BrowseField
  onNavigate?: () => void
}) {
  const view = useView()
  const [open, setOpen] = useState(false)
  const [narrow, setNarrow] = useState('')
  const [all, setAll] = useState(false)
  const items = useBrowseField(library, field.key, view.vl, open)
  const active = view.filters.filter((f) =>
    f.startsWith(field.key + ':'),
  ).length

  const shown = useMemo(() => {
    const list = items.data ?? []
    const n = narrow.trim().toLocaleLowerCase()
    return n ? list.filter((i) => i.name.toLocaleLowerCase().includes(n)) : list
  }, [items.data, narrow])

  const toggle = (search: string) => {
    const filters = view.filters.includes(search)
      ? view.filters.filter((f) => f !== search)
      : [...view.filters, search]
    setView(resetFor({ filters }))
    onNavigate?.()
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-sidebar-foreground/90 outline-none hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-sidebar-ring"
      >
        <IconChevronRight
          className={cn(
            'size-4 shrink-0 opacity-60 transition-transform',
            open && 'rotate-90',
          )}
        />
        <span className="min-w-0 flex-1 truncate">{field.name}</span>
        {active > 0 && (
          <IconFilter className="size-3.5 text-muted-foreground" />
        )}
      </button>
      {open && (
        <div className="mb-1 ml-4 border-l pl-2">
          {items.isPending && (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">
              Loading…
            </p>
          )}
          {items.isError && (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">
              This list could not be loaded.
            </p>
          )}
          {(items.data?.length ?? 0) > 12 && (
            <Input
              value={narrow}
              onChange={(e) => setNarrow(e.target.value)}
              placeholder={`Find in ${field.name.toLocaleLowerCase()}`}
              aria-label={`Find in ${field.name}`}
              className="my-1 h-7 text-xs"
            />
          )}
          {items.data?.length === 0 && (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">
              Nothing here yet.
            </p>
          )}
          {(all || narrow ? shown : shown.slice(0, SHOWN)).map((item) => {
            const on = view.filters.includes(item.search)
            return (
              <Row
                key={item.search}
                active={on}
                onClick={() => toggle(item.search)}
                count={item.count}
                icon={
                  on ? <IconCheck className="size-3.5 shrink-0" /> : undefined
                }
              >
                {item.name}
              </Row>
            )
          })}
          {!all && !narrow && shown.length > SHOWN && (
            <button
              type="button"
              onClick={() => setAll(true)}
              className="px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground"
            >
              Show all {formatCount(shown.length)}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
