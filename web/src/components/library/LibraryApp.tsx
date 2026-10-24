// The library: the sidebar, the top bar, the books as a grid or a list, and
// one book's details over them. Everything on screen comes from the address
// bar (lib/state.ts) and calibre's endpoints (lib/queries.ts).
import { useEffect, useRef, useState } from 'react'
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-react'
import type { BookQuery } from '@/lib/api'
import { app } from '@/lib/base'
import { useRememberedView } from '@/lib/prefs'
import { useBookList, useLibrary, useServerInfo } from '@/lib/queries'
import { combinedSearch, resetFor, setView, useView } from '@/lib/state'
import { AppProviders } from '@/components/app/AppProviders'
import { Button } from '@/components/ui/button'
import { Toaster } from '@/components/ui/sonner'
import { EditBook } from '@/components/edit/EditBook'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from '@/components/ui/sheet'
import { BookDetails } from './BookDetails'
import { BookGrid } from './BookGrid'
import { BookRows } from './BookRows'
import { Sidebar } from './Sidebar'
import { StatusLine } from './StatusLine'
import { DEFAULT_SORT, TopBar } from './TopBar'

export default function LibraryApp() {
  return (
    <AppProviders keep>
      <Library />
      <Toaster position="bottom-center" />
    </AppProviders>
  )
}

function Library() {
  const view = useView()
  const server = useServerInfo()
  const map = server.data?.library_map ?? {}
  const library = server.data
    ? view.library in map
      ? view.library
      : server.data.default_library_id
    : undefined
  const info = useLibrary(library)
  const [menuOpen, setMenuOpen] = useState(false)
  useRememberedView(library)

  const query: BookQuery | null = library
    ? {
        library,
        search: combinedSearch(view),
        sort: view.sort || DEFAULT_SORT,
        order: view.sort ? view.order : 'desc',
        vl: view.vl,
      }
    : null
  // The first page is shared with the grid or list below; this only reads
  // the count from it.
  const list = useBookList(query, [0, 0])

  useEffect(() => {
    const name = library ? map[library] : ''
    document.title = name ? `${name} · Calibre Zen` : 'Calibre Zen'
  }, [library, map])

  // A book opened here closes with Back; one opened from a link closes in place.
  const openedHere = useRef(false)
  const open = (id: number) => {
    openedHere.current = true
    setView({ book: id })
  }
  const close = () => {
    if (openedHere.current) {
      openedHere.current = false
      history.back()
    } else {
      setView({ book: null }, { replace: true })
    }
  }

  if (server.isError) {
    return (
      <Problem
        text="The server could not be reached, or did not let this browser in."
        retry={() => void server.refetch()}
      />
    )
  }
  // Offline, with nothing kept from an earlier visit: the requests wait for
  // the network rather than failing.
  const paused = (q: typeof info | typeof server) =>
    q.isPending && q.fetchStatus === 'paused'
  if (paused(server) || paused(info)) {
    return (
      <Problem
        text="You are offline, and this library has not been opened in this browser before."
        retry={() => location.reload()}
      />
    )
  }

  const sidebar = (
    <>
      <a href={app()} className="flex items-center gap-2.5 px-5 pt-4 pb-1">
        <img src={app('icon.svg')} alt="" className="size-7 rounded-lg" />
        <span className="font-semibold tracking-tight">Calibre Zen</span>
      </a>
      {library && (
        <Sidebar
          library={library}
          info={info.data}
          onNavigate={() => setMenuOpen(false)}
        />
      )}
    </>
  )

  return (
    <div className="flex h-dvh overflow-hidden">
      <aside className="hidden w-64 shrink-0 flex-col overflow-y-auto border-r bg-sidebar md:flex">
        {sidebar}
      </aside>
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent
          side="left"
          className="w-72 overflow-y-auto bg-sidebar p-0"
        >
          <SheetTitle className="sr-only">Libraries and filters</SheetTitle>
          <SheetDescription className="sr-only">
            Choose what the list shows.
          </SheetDescription>
          {sidebar}
        </SheetContent>
      </Sheet>

      <main className="flex min-w-0 flex-1 flex-col">
        <TopBar
          library={library}
          info={info.data}
          onMenu={() => setMenuOpen(true)}
        />
        <StatusLine info={info.data} total={list.total} />
        {query && list.total === 0 && !list.stale ? (
          <Empty />
        ) : query && view.mode === 'list' ? (
          <BookRows query={query} selected={view.book} onOpen={open} />
        ) : query ? (
          <BookGrid query={query} selected={view.book} onOpen={open} />
        ) : null}
      </main>

      <Sheet open={!!view.book} onOpenChange={(o) => !o && close()}>
        <SheetContent
          side="right"
          className="w-full overflow-y-auto p-0 sm:max-w-md"
        >
          <SheetTitle className="sr-only">Book details</SheetTitle>
          <SheetDescription className="sr-only">
            The book&rsquo;s details and files.
          </SheetDescription>
          {library && view.book && (
            <BookDetails library={library} info={info.data} id={view.book} />
          )}
        </SheetContent>
      </Sheet>
      {library && <EditBook library={library} info={info.data} />}
    </div>
  )
}

function Empty() {
  const view = useView()
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
      <p className="text-sm text-muted-foreground">
        {view.q || view.filters.length
          ? 'No books match.'
          : 'There are no books here yet.'}
      </p>
      {(view.q || view.filters.length > 0 || view.vl) && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setView(resetFor({ q: '', filters: [], vl: '' }))}
        >
          Show all books
        </Button>
      )}
    </div>
  )
}

function Problem({ text, retry }: { text: string; retry: () => void }) {
  return (
    <div className="flex h-dvh flex-col items-center justify-center gap-3 p-8 text-center">
      <IconAlertTriangle className="size-6 text-muted-foreground" />
      <p className="max-w-sm text-sm">{text}</p>
      <Button variant="outline" size="sm" onClick={retry}>
        <IconRefresh />
        Try again
      </Button>
    </div>
  )
}
