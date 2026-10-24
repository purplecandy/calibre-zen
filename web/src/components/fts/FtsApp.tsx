// /app/search/?library=books&q=marmalade: searching the words inside the
// books, with the passages that matched. The search is kept in the address,
// so back works and a search is a link.
import { useEffect, useState, type ReactNode } from 'react'
import { useMutation, useQueries, useQuery } from '@tanstack/react-query'
import {
  IconAlertTriangle,
  IconDotsVertical,
  IconFileSearch,
  IconSearch,
} from '@tabler/icons-react'
import { ServerError, type Book } from '@/lib/api'
import { app } from '@/lib/base'
import { books, formatCount } from '@/lib/format'
import {
  disableFts,
  enableFts,
  ftsProblem,
  ftsSearch,
  ftsSnippets,
  reindex,
  snippetParts,
  type FtsQuery,
} from '@/lib/fts'
import { useOnline } from '@/lib/offline'
import { setSetting, useSetting } from '@/lib/prefs'
import { queryClient, useLibrary, useServerInfo } from '@/lib/queries'
import { AppProviders } from '@/components/app/AppProviders'
import { PageHeader } from '@/components/app/PageHeader'
import { Cover } from '@/components/library/Cover'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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

function readAddress(): Address {
  const p = new URLSearchParams(location.search)
  return {
    library: p.get('library') ?? '',
    q: p.get('q') ?? '',
    restrict: p.get('in') ?? '',
  }
}

function writeAddress(a: Address) {
  const p = new URLSearchParams()
  if (a.library) p.set('library', a.library)
  if (a.q) p.set('q', a.q)
  if (a.restrict) p.set('in', a.restrict)
  history.pushState(null, '', location.pathname + '?' + p.toString())
}

function useAddress(): [Address, (a: Address) => void] {
  const [address, setAddress] = useState(readAddress)
  useEffect(() => {
    const onPop = () => setAddress(readAddress())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  return [
    address,
    (a) => {
      writeAddress(a)
      setAddress(a)
    },
  ]
}

function libraryLink(library: string, extra = '') {
  return app(`?library=${encodeURIComponent(library)}${extra}`)
}

function FullTextSearch() {
  const server = useServerInfo()
  const [address, setAddress] = useAddress()
  const map = server.data?.library_map ?? {}
  const library = server.data
    ? address.library in map
      ? address.library
      : server.data.default_library_id
    : undefined
  const info = useLibrary(library)
  const related = useSetting('ftsRelated')
  const online = useOnline()

  const [text, setText] = useState(address.q)
  const [restrict, setRestrict] = useState(address.restrict)
  const [showRestrict, setShowRestrict] = useState(!!address.restrict)
  useEffect(() => {
    setText(address.q)
    setRestrict(address.restrict)
  }, [address.q, address.restrict])

  useEffect(() => {
    const name = library ? map[library] : ''
    document.title = name
      ? `Search book text · ${name} · Calibre Zen`
      : 'Search book text · Calibre Zen'
  }, [library, map])

  const enabled = info.data?.fts_enabled
  const query: FtsQuery | null =
    library && address.q && enabled
      ? { library, query: address.q, related, restrict: address.restrict }
      : null

  return (
    <div className="min-h-dvh">
      <PageHeader
        back={library ? libraryLink(library) : app()}
        backLabel="Back to the library"
        title="Search book text"
      >
        {library && enabled && <IndexMenu library={library} />}
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

        {info.data && !enabled && library && (
          <TurnOn library={library} name={map[library]} online={online} />
        )}
        {query && <Results query={query} />}
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

function TurnOn({
  library,
  name,
  online,
}: {
  library: string
  name: string | undefined
  online: boolean
}) {
  const turnOn = useMutation({
    mutationFn: () => enableFts(library),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['library', library] }),
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
        disabled={!online || turnOn.isPending}
        onClick={() => turnOn.mutate()}
      >
        Turn on full-text search
      </Button>
      {turnOn.isError && (
        <p role="alert" className="text-sm text-destructive">
          {ftsProblem(turnOn.error)}
        </p>
      )}
    </div>
  )
}

function Results({ query }: { query: FtsQuery }) {
  const results = useQuery({
    queryKey: ['fts', query],
    queryFn: () => ftsSearch(query),
    // While calibre is still reading books, new matches turn up.
    refetchInterval: (q) =>
      (q.state.data?.indexing_status.left ?? 0) > 0 ? 5000 : false,
    retry: (n, e) => n < 1 && !(e instanceof ServerError),
  })
  const [shown, setShown] = useState(BATCH)
  useEffect(() => setShown(BATCH), [query])

  if (results.isPending) {
    return <p className="text-sm text-muted-foreground">Searching…</p>
  }
  if (results.isError) {
    return (
      <Alert variant="destructive">
        <IconAlertTriangle />
        <AlertTitle>The search did not run</AlertTitle>
        <AlertDescription>{ftsProblem(results.error)}</AlertDescription>
      </Alert>
    )
  }

  const d = results.data
  // One result per book, with each format the words were found in.
  const byBook = new Map<number, string[]>()
  for (const r of d.results) {
    byBook.set(r.book_id, [...(byBook.get(r.book_id) ?? []), r.format])
  }
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
        {chunks(ids.slice(0, shown), BATCH).map((chunk) => (
          <Batch
            key={chunk.join(',')}
            query={query}
            ids={chunk}
            formats={byBook}
            metadata={d.metadata}
          />
        ))}
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

function chunks<T>(list: T[], n: number): T[][] {
  const out: T[][] = []
  for (let i = 0; i < list.length; i += n) out.push(list.slice(i, i + n))
  return out
}

function Batch({
  query,
  ids,
  formats,
  metadata,
}: {
  query: FtsQuery
  ids: number[]
  formats: Map<number, string[]>
  metadata: Record<string, { title: string; authors: string }>
}) {
  const [snippets] = useQueries({
    queries: [
      {
        queryKey: ['fts-snippets', query, ids],
        queryFn: () => ftsSnippets(query, ids),
        staleTime: Infinity,
      },
    ],
  })
  return (
    <>
      {ids.map((id) => (
        <Result
          key={id}
          library={query.library}
          id={id}
          title={metadata[id]?.title ?? ''}
          authors={metadata[id]?.authors ?? ''}
          formats={formats.get(id) ?? []}
          passages={
            snippets.data
              ? (snippets.data[id]?.map((s) => s.text) ?? [])
              : undefined
          }
        />
      ))}
    </>
  )
}

function Result({
  library,
  id,
  title,
  authors,
  formats,
  passages,
}: {
  library: string
  id: number
  title: string
  authors: string
  formats: string[]
  passages: string[] | undefined
}) {
  const book: Book & { id: number } = { id, title }
  const href = libraryLink(library, `&book=${id}`)
  return (
    <li className="flex gap-4 rounded-xl border p-4">
      <a href={href} className="w-14 shrink-0 sm:w-16" tabIndex={-1}>
        <Cover library={library} book={book} width={64} />
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
          <ResultMenu library={library} id={id} />
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

function ResultMenu({ library, id }: { library: string; id: number }) {
  const online = useOnline()
  const [message, setMessage] = useState('')
  const again = useMutation({
    mutationFn: () => reindex(library, id),
    onSuccess: () => setMessage('This book will be read again shortly.'),
    onError: (e) => setMessage(ftsProblem(e)),
  })
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
            <a href={libraryLink(library, `&book=${id}`)}>Show the book</a>
          </DropdownMenuItem>
          <DropdownMenuItem disabled={!online} onSelect={() => again.mutate()}>
            Read this book again
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={!!message} onOpenChange={(o) => !o && setMessage('')}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Read this book again</DialogTitle>
            <DialogDescription>{message}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button>OK</Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

/** Read every book again, or turn full-text search off. */
function IndexMenu({ library }: { library: string }) {
  const online = useOnline()
  const [confirm, setConfirm] = useState<'all' | 'off' | null>(null)
  const [error, setError] = useState('')
  const act = useMutation({
    mutationFn: (what: 'all' | 'off') =>
      what === 'all' ? reindex(library) : disableFts(library),
    onSuccess: () => {
      setConfirm(null)
      void queryClient.invalidateQueries({ queryKey: ['library', library] })
      void queryClient.invalidateQueries({ queryKey: ['fts'] })
    },
    onError: (e) => setError(ftsProblem(e)),
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
      <Dialog
        open={!!confirm}
        onOpenChange={(o) => {
          if (!o) {
            setConfirm(null)
            setError('')
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{c?.title}</DialogTitle>
            <DialogDescription>{c?.body}</DialogDescription>
          </DialogHeader>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              variant={confirm === 'off' ? 'destructive' : 'default'}
              disabled={act.isPending}
              onClick={() => confirm && act.mutate(confirm)}
            >
              {c?.button}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
