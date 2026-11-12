// /app/search/?library=books&q=marmalade: searching the words inside the
// books, with the passages that matched. The search is kept in the address,
// so back works and a search is a link.
import { useEffect, useState, type ReactNode } from 'react'
import {
  IconDotsVertical,
  IconFileSearch,
  IconSearch,
} from '@tabler/icons-react'
import { useAction } from '@/lib/action'
import type { Book } from '@/lib/api'
import { app } from '@/lib/base'
import { books, formatCount } from '@/lib/format'
import {
  disableFts,
  enableFts,
  FTS_ERRORS,
  reindex,
  type FtsQuery,
} from '@/lib/fts'
import {
  useCurrentLibrary,
  useDocumentTitle,
  useEventListener,
  useOnline,
} from '@/lib/hooks'
import { batches, formatsByBook, snippetParts } from '@/lib/model/fts'
import { setSetting, useSetting } from '@/lib/prefs'
import {
  ftsChanged,
  ftsTurnedOn,
  useFtsSearch,
  useFtsSnippets,
  useServerInfo,
} from '@/lib/queries'
import { bookLink, libraryLink, readAddress, writeAddress } from '@/lib/url'
import { AppProviders } from '@/components/app/AppProviders'
import { ConfirmDialog, FormDialog } from '@/components/app/Dialogs'
import {
  LibraryProvider,
  useLibraryContext,
} from '@/components/app/LibraryContext'
import { PageHeader } from '@/components/app/PageHeader'
import { Section } from '@/components/app/Section'
import { Cover } from '@/components/library/Cover'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Switch } from '@/components/ui/switch'

export default function FtsApp() {
  return (
    <AppProviders>
      <FullTextSearch />
    </AppProviders>
  )
}

/** Results shown at a time; each batch fetches its passages when shown. */
const BATCH = 20

interface Address {
  library: string
  q: string
  restrict: string
}

function parseAddress(): Address {
  const p = readAddress()
  return {
    library: p.get('library') ?? '',
    q: p.get('q') ?? '',
    restrict: p.get('in') ?? '',
  }
}

function useAddress(): [Address, (a: Address) => void] {
  const [address, setAddress] = useState(parseAddress)
  useEventListener(window, 'popstate', () => setAddress(parseAddress()))
  return [
    address,
    (a) => {
      writeAddress({ library: a.library, q: a.q, in: a.restrict })
      setAddress(a)
    },
  ]
}

function FullTextSearch() {
  const [address, setAddress] = useAddress()
  const library = useCurrentLibrary(address.library)
  return (
    <LibraryProvider library={library}>
      <Search address={address} setAddress={setAddress} />
    </LibraryProvider>
  )
}

function Search({
  address,
  setAddress,
}: {
  address: Address
  setAddress: (a: Address) => void
}) {
  const { library, info } = useLibraryContext()
  const map = useServerInfo().library_map
  const related = useSetting('ftsRelated')

  const [text, setText] = useState(address.q)
  const [restrict, setRestrict] = useState(address.restrict)
  const [showRestrict, setShowRestrict] = useState(!!address.restrict)
  useEffect(() => {
    setText(address.q)
    setRestrict(address.restrict)
  }, [address.q, address.restrict])

  useDocumentTitle('Search book text', library && map[library])

  const enabled = info.fts_enabled
  const query: FtsQuery | null =
    address.q && enabled
      ? { library, query: address.q, related, restrict: address.restrict }
      : null

  return (
    <div className="min-h-dvh">
      <PageHeader
        back={library ? libraryLink(library) : app()}
        backLabel="Back to the library"
        title="Search book text"
      >
        {library && enabled && <IndexMenu />}
      </PageHeader>
      <main className="mx-auto grid max-w-3xl gap-5 px-4 py-6 sm:px-6">
        {library && enabled && (
          <form
            role="search"
            className="grid gap-3"
            onSubmit={(e) => {
              e.preventDefault()
              setAddress({
                library,
                q: text.trim(),
                restrict: showRestrict ? restrict.trim() : '',
              })
            }}
          >
            <div className="flex gap-2">
              <div className="relative min-w-0 flex-1">
                <IconSearch className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="search"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Words or a phrase from inside a book"
                  aria-label="Search the text of the books"
                  className="pl-8"
                  enterKeyHint="search"
                  autoFocus
                />
              </div>
              <Button type="submit" disabled={!text.trim() || !enabled}>
                Search
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
              <Label className="font-normal">
                <Switch
                  checked={related}
                  onCheckedChange={(v) => setSetting('ftsRelated', v)}
                />
                Match related words
              </Label>
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground"
                aria-expanded={showRestrict}
                onClick={() => setShowRestrict((s) => !s)}
              >
                {showRestrict ? 'Search all books' : 'Search only some books'}
              </button>
            </div>
            {showRestrict && (
              <Input
                value={restrict}
                onChange={(e) => setRestrict(e.target.value)}
                placeholder="Only books matching a search, such as tags:fiction"
                aria-label="Only in books matching"
              />
            )}
          </form>
        )}

        {!enabled && <TurnOn />}
        {query && (
          <Section
            failed="The search did not run."
            wording={FTS_ERRORS}
            resetKeys={[JSON.stringify(query)]}
            loading={
              <p className="text-sm text-muted-foreground" role="status">
                Searching…
              </p>
            }
          >
            <Results query={query} />
          </Section>
        )}
        {enabled && !address.q && <Help />}
      </main>
    </div>
  )
}

function Help() {
  return (
    <div className="grid gap-2 text-sm text-muted-foreground">
      <p>
        Type a few words to find the books that contain them. Put a phrase in
        quotes to find those words together.
      </p>
      <p>
        Use <code>AND</code>, <code>OR</code> and <code>NOT</code> to combine
        words, and <code>*</code> at the end of a word to match its start, as in{' '}
        <code>light*</code>.
      </p>
    </div>
  )
}

function TurnOn() {
  const { library } = useLibraryContext()
  const name = useServerInfo().library_map[library]
  const online = useOnline()
  const turnOn = useAction({
    run: () => enableFts(library),
    after: () => ftsTurnedOn(library),
    failure: 'inline',
    wording: FTS_ERRORS,
  })
  return (
    <div className="grid justify-items-start gap-3 rounded-xl border p-5">
      <IconFileSearch className="size-6 text-muted-foreground" />
      <h2 className="font-medium">
        Full-text search is off for {name ?? 'this library'}
      </h2>
      <p className="text-sm text-muted-foreground">
        Turning it on lets you search the words inside every book. calibre reads
        each book once in the background, which takes a while for a big library.
      </p>
      <Button
        disabled={!online || turnOn.busy}
        onClick={() => void turnOn.run()}
      >
        Turn on full-text search
      </Button>
      {turnOn.error && (
        <p role="alert" className="text-sm text-destructive">
          {turnOn.error}
        </p>
      )}
    </div>
  )
}

function Results({ query }: { query: FtsQuery }) {
  const d = useFtsSearch(query)
  const [shown, setShown] = useState(BATCH)
  useEffect(() => setShown(BATCH), [query])

  // One result per book, with each format the words were found in.
  const byBook = formatsByBook(d.results)
  const ids = [...byBook.keys()]
  const { left, total } = d.indexing_status

  return (
    <div className="grid gap-4">
      {left > 0 && (
        <div className="grid gap-2 rounded-lg border p-4 text-sm">
          <p>
            calibre has read {formatCount(total - left)} of {formatCount(total)}{' '}
            files so far. Some matches may be missing until it is done.
          </p>
          <Progress
            value={total ? ((total - left) / total) * 100 : 0}
            aria-label="Books read so far"
          />
        </div>
      )}
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {ids.length === 0
          ? left > 0
            ? 'No books contain these words yet.'
            : 'No books contain these words.'
          : `Found in ${books(ids.length)}`}
      </p>
      <ol className="grid gap-3">
        {batches(ids, shown, BATCH).map((batch) => {
          const props = {
            query,
            ids: batch,
            formats: byBook,
            metadata: d.metadata,
          }
          // A batch's passages are asked for when it is shown; until they
          // are in, its books are there without them.
          return (
            <Section
              key={batch.join(',')}
              size="inline"
              wording={FTS_ERRORS}
              loading={<Batch {...props} />}
            >
              <WithPassages {...props} />
            </Section>
          )
        })}
      </ol>
      {ids.length > shown && (
        <Button
          variant="outline"
          className="justify-self-center"
          onClick={() => setShown((n) => n + BATCH)}
        >
          Show more
        </Button>
      )}
    </div>
  )
}

interface BatchProps {
  query: FtsQuery
  ids: number[]
  formats: Map<number, string[]>
  metadata: Record<string, { title: string; authors: string }>
}

function WithPassages(props: BatchProps) {
  const snippets = useFtsSnippets(props.query, props.ids)
  return <Batch {...props} snippets={snippets} />
}

function Batch({
  ids,
  formats,
  metadata,
  snippets,
}: BatchProps & { snippets?: Record<string, { text: string }[]> }) {
  return (
    <>
      {ids.map((id) => (
        <Result
          key={id}
          id={id}
          title={metadata[id]?.title ?? ''}
          authors={metadata[id]?.authors ?? ''}
          formats={formats.get(id) ?? []}
          passages={
            snippets ? (snippets[id]?.map((s) => s.text) ?? []) : undefined
          }
        />
      ))}
    </>
  )
}

function Result({
  id,
  title,
  authors,
  formats,
  passages,
}: {
  id: number
  title: string
  authors: string
  formats: string[]
  passages: string[] | undefined
}) {
  const { library } = useLibraryContext()
  const book: Book & { id: number } = { id, title }
  const href = bookLink(library, id)
  return (
    <li className="flex gap-4 rounded-xl border p-4">
      <a href={href} className="w-14 shrink-0 sm:w-16" tabIndex={-1}>
        <Cover book={book} width={64} />
      </a>
      <div className="grid min-w-0 flex-1 content-start gap-1.5">
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <a
              href={href}
              className="font-serif text-lg leading-tight font-medium hover:underline"
            >
              {title}
            </a>
            <p className="text-sm text-muted-foreground">
              {authors}
              {formats.length > 0 && (
                <span className="ml-2 text-xs">{formats.join(', ')}</span>
              )}
            </p>
          </div>
          <ResultMenu id={id} />
        </div>
        {passages === undefined ? (
          <p className="text-sm text-muted-foreground">Finding the passages…</p>
        ) : (
          passages.slice(0, 3).map((p, i) => <Passage key={i} text={p} />)
        )}
      </div>
    </li>
  )
}

function Passage({ text }: { text: string }) {
  const parts: ReactNode[] = snippetParts(text).map((part, i) =>
    part.match ? (
      <mark
        key={i}
        className="rounded-sm bg-primary/15 px-0.5 font-medium text-foreground"
      >
        {part.text}
      </mark>
    ) : (
      part.text
    ),
  )
  return (
    <p className="line-clamp-4 text-sm leading-relaxed text-muted-foreground">
      {parts}
    </p>
  )
}

function ResultMenu({ id }: { id: number }) {
  const { library } = useLibraryContext()
  const online = useOnline()
  const [queued, setQueued] = useState(false)
  const again = useAction({
    run: () => reindex(library, id).then(() => true),
    failure: 'inline',
    wording: FTS_ERRORS,
  })
  const message = queued ? 'This book will be read again shortly.' : again.error
  const close = () => {
    setQueued(false)
    again.reset()
  }
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={`More for this book`}>
            <IconDotsVertical className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <a href={bookLink(library, id)}>Show the book</a>
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={!online}
            onSelect={async () => {
              if (await again.run()) setQueued(true)
            }}
          >
            Read this book again
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <FormDialog
        open={!!message}
        onOpenChange={(o) => !o && close()}
        title="Read this book again"
        description={message}
        size="sm"
        footer={<Button onClick={close}>OK</Button>}
      />
    </>
  )
}

/** Read every book again, or turn full-text search off. */
function IndexMenu() {
  const { library } = useLibraryContext()
  const online = useOnline()
  const [confirm, setConfirm] = useState<'all' | 'off' | null>(null)
  const act = useAction({
    run: (what: 'all' | 'off') =>
      (what === 'all' ? reindex(library) : disableFts(library)).then(
        () => true,
      ),
    after: () => ftsChanged(library),
    failure: 'inline',
    wording: FTS_ERRORS,
  })
  const copy = {
    all: {
      title: 'Read every book again?',
      body: 'calibre reads each book in the library again in the background. For a big library this takes a long time.',
      button: 'Read them again',
    },
    off: {
      title: 'Turn off full-text search?',
      body: 'The words calibre has read are thrown away. Turning it back on means reading every book again.',
      button: 'Turn it off',
    },
  }
  const c = confirm ? copy[confirm] : null
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Full-text search settings"
          >
            <IconDotsVertical className="size-5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            disabled={!online}
            onSelect={() => setConfirm('all')}
          >
            Read every book again
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={!online}
            onSelect={() => setConfirm('off')}
          >
            Turn off full-text search
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmDialog
        open={!!confirm}
        onOpenChange={(o) => {
          if (!o) {
            setConfirm(null)
            act.reset()
          }
        }}
        title={c?.title}
        description={c?.body}
        confirm={c?.button ?? ''}
        destructive={confirm === 'off'}
        onConfirm={async () => {
          if (confirm && (await act.run(confirm))) setConfirm(null)
        }}
      >
        {act.error && (
          <p role="alert" className="text-sm text-destructive">
            {act.error}
          </p>
        )}
      </ConfirmDialog>
    </>
  )
}
