// The library: the sidebar, the top bar, the books as a grid or a list, and
// one book's details over them. Everything on screen comes from the address
// bar (lib/state.ts) and calibre's endpoints (lib/queries).
import { useDeferredValue, useState } from 'react'
import type { BookQuery } from '@/lib/api'
import { app } from '@/lib/base'
import { useCurrentLibrary, useDocumentTitle } from '@/lib/hooks'
import { DEFAULT_SORT } from '@/lib/model/fields'
import { useRememberedView } from '@/lib/prefs'
import { useBookList, useServerInfo } from '@/lib/queries'
import {
  closeStep,
  combinedSearch,
  openStep,
  resetFor,
  setView,
  useView,
  type ViewState,
} from '@/lib/state'
import { Credit } from '@/components/app/About'
import { AppProviders } from '@/components/app/AppProviders'
import { LibraryProvider } from '@/components/app/LibraryContext'
import { Empty, Section } from '@/components/app/Section'
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
import { TopBar } from './TopBar'

export default function LibraryApp() {
  return (
    <AppProviders
      keep
      offline="You are offline, and this library has not been opened in this browser before."
      wording={{ server: () => NO_SERVER, other: NO_SERVER }}
    >
      <Library />
      <Toaster position="bottom-center" />
    </AppProviders>
  )
}

const NO_SERVER =
  'The server could not be reached, or did not let this browser in.'

/** The books a view asks for. */
function bookQuery(view: ViewState, library: string): BookQuery {
  return {
    library,
    search: combinedSearch(view),
    sort: view.sort || DEFAULT_SORT,
    order: view.sort ? view.order : 'desc',
    vl: view.vl,
  }
}

function Library() {
  const view = useView()
  // What is on screen follows the address a step behind, so the books shown
  // stay while the next ones load, instead of the list blanking at every
  // letter typed into the search box.
  const shown = useDeferredValue(view)
  const server = useServerInfo()
  const library = useCurrentLibrary(shown.library)
  const [menuOpen, setMenuOpen] = useState(false)
  useRememberedView(library)

  const query = bookQuery(shown, library)
  const next = bookQuery(view, useCurrentLibrary(view.library))
  const stale = JSON.stringify(query) !== JSON.stringify(next)

  useDocumentTitle(server.library_map[library])

  // A book opened here closes with Back; one opened from a link closes in place.
  const open = (id: number) => openStep('book', { book: id })
  const close = () => closeStep('book', { book: null })

  const sidebar = (
    <>
      <a href={app()} className="flex items-center gap-2.5 px-5 pt-4 pb-1">
        <img src={app('icon.svg')} alt="" className="size-7 rounded-lg" />
        <span className="font-semibold tracking-tight">Calibre Zen</span>
      </a>
      <Sidebar onNavigate={() => setMenuOpen(false)} />
      <Credit />
    </>
  )

  // The library shown is the deferred one, so its books and fields stay on
  // screen while another library's load.
  return (
    <LibraryProvider library={library}>
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
          <TopBar onMenu={() => setMenuOpen(true)} />
          <Section
            failed="These books could not be shown."
            wording={{ status: { 400: NOT_FIT, 404: NOT_FIT, 422: NOT_FIT } }}
            // A sort, virtual library or search this library does not have,
            // usually from an old link: calibre answers with an error, so the
            // plain view is offered instead.
            reset={{
              label: 'Show all books',
              run: () =>
                setView(
                  resetFor({
                    q: '',
                    filters: [],
                    vl: '',
                    sort: '',
                    order: 'desc',
                  }),
                ),
            }}
            resetKeys={[JSON.stringify(query)]}
          >
            <Books
              query={query}
              mode={shown.mode}
              stale={stale}
              selected={view.book}
              onOpen={open}
            />
          </Section>
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
            {view.book && (
              <Section
                key={`${library}:${view.book}`}
                failed="This book could not be loaded."
              >
                <BookDetails id={view.book} />
              </Section>
            )}
          </SheetContent>
        </Sheet>
        <EditBook />
      </div>
    </LibraryProvider>
  )
}

const NOT_FIT = 'The sort or filter may not fit this library.'

/** The count and the filters in force, over the books as a grid or a list. */
function Books({
  query,
  mode,
  stale,
  selected,
  onOpen,
}: {
  query: BookQuery
  mode: ViewState['mode']
  stale: boolean
  selected: number | null
  onOpen: (id: number) => void
}) {
  // The first page is shared with the grid or list below; this only reads
  // the count from it.
  const { total } = useBookList(query, [0, 0])
  return (
    <>
      <StatusLine total={total} />
      {total === 0 && !stale ? (
        <NoBooks />
      ) : mode === 'list' ? (
        <BookRows
          query={query}
          stale={stale}
          selected={selected}
          onOpen={onOpen}
        />
      ) : (
        <BookGrid
          query={query}
          stale={stale}
          selected={selected}
          onOpen={onOpen}
        />
      )}
    </>
  )
}

function NoBooks() {
  const view = useView()
  return (
    <Empty
      text={
        view.q || view.filters.length
          ? 'No books match.'
          : 'There are no books here yet.'
      }
      action={
        view.q || view.filters.length > 0 || view.vl
          ? {
              label: 'Show all books',
              run: () => setView(resetFor({ q: '', filters: [], vl: '' })),
            }
          : undefined
      }
    />
  )
}
