import { useEffect, useRef, useState } from 'react'
import {
  IconArrowsSort,
  IconLayoutGrid,
  IconList,
  IconMenu2,
  IconSearch,
  IconX,
} from '@tabler/icons-react'
import type { LibraryInfo } from '@/lib/api'
import { setView, useView, type Mode } from '@/lib/state'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { AppMenu } from './AppMenu'

// Fields where newest or highest first is what someone means by sorting.
const DESCENDING = new Set([
  'timestamp',
  'pubdate',
  'last_modified',
  'rating',
  'size',
  'id',
])
export const DEFAULT_SORT = 'timestamp'

function SearchBox() {
  const view = useView()
  const [text, setText] = useState(view.q)
  const input = useRef<HTMLInputElement>(null)

  // Back, forward and a cleared chip change the search from outside.
  useEffect(() => setText(view.q), [view.q])

  useEffect(() => {
    if (text === view.q) return
    const t = setTimeout(
      () => setView({ q: text, book: null }, { replace: true }),
      350,
    )
    return () => clearTimeout(t)
  }, [text, view.q])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (e.key === '/' && !el.closest('input, textarea, [contenteditable]')) {
        e.preventDefault()
        input.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <form
      role="search"
      className="relative min-w-0 flex-1 sm:max-w-md"
      onSubmit={(e) => {
        e.preventDefault()
        setView({ q: text, book: null })
      }}
    >
      <IconSearch className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        ref={input}
        type="search"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Search"
        aria-label="Search the library"
        className="pr-8 pl-8 [&::-webkit-search-cancel-button]:hidden"
        enterKeyHint="search"
      />
      {text && (
        <button
          type="button"
          aria-label="Clear the search"
          onClick={() => {
            setText('')
            setView({ q: '', book: null })
          }}
          className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:text-foreground"
        >
          <IconX className="size-4" />
        </button>
      )}
    </form>
  )
}

function SortMenu({ info }: { info: LibraryInfo | undefined }) {
  const view = useView()
  const sort = view.sort || DEFAULT_SORT
  const order = view.sort ? view.order : 'desc'
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Sort">
          <IconArrowsSort className="size-5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="max-h-[70dvh] w-56 overflow-y-auto"
      >
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
          Sort by
        </DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={sort}
          onValueChange={(f) =>
            setView({
              sort: f,
              order: DESCENDING.has(f) ? 'desc' : 'asc',
              book: null,
            })
          }
        >
          {(info?.sortable_fields ?? []).map(([key, name]) => (
            <DropdownMenuRadioItem key={key} value={key}>
              {key === 'timestamp' ? 'Date added' : name}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuRadioGroup
          value={order}
          onValueChange={(o) =>
            setView({ sort, order: o as 'asc' | 'desc', book: null })
          }
        >
          <DropdownMenuRadioItem value="asc">Ascending</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="desc">Descending</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function TopBar({
  info,
  onMenu,
}: {
  info: LibraryInfo | undefined
  onMenu: () => void
}) {
  const view = useView()
  return (
    <header className="flex items-center gap-1.5 border-b px-3 py-2.5 sm:gap-2 sm:px-4">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="Show libraries and filters"
        onClick={onMenu}
      >
        <IconMenu2 className="size-5" />
      </Button>
      <SearchBox />
      <div className="ml-auto flex items-center gap-1">
        <ToggleGroup
          type="single"
          value={view.mode}
          onValueChange={(m) =>
            m && setView({ mode: m as Mode }, { replace: true })
          }
          className="hidden sm:flex"
          aria-label="Show as"
        >
          <ToggleGroupItem value="grid" aria-label="Grid">
            <IconLayoutGrid className="size-4" />
          </ToggleGroupItem>
          <ToggleGroupItem value="list" aria-label="List">
            <IconList className="size-4" />
          </ToggleGroupItem>
        </ToggleGroup>
        <SortMenu info={info} />
        <AppMenu />
      </div>
    </header>
  )
}
