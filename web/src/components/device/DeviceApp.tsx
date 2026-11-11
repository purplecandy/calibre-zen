// /app/device/: the books calibre's reader keeps in this browser. They open
// with no network, so this page needs none either: it reads the browser's
// own storage, and the server only adds the libraries' names when it can.
import { useEffect, useState } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { IconArrowLeft, IconBook, IconTrash } from '@tabler/icons-react'
import { app } from '@/lib/base'
import { deviceCover, removeDeviceBook, type DeviceBook } from '@/lib/device'
import { books, formatDate, seriesText } from '@/lib/format'
import { queryClient, useServerInfo } from '@/lib/queries'
import { readerUrl } from '@/lib/reader'
import { refreshDeviceBooks, useDeviceBooks } from '@/lib/reading'
import { Button } from '@/components/ui/button'

export default function DeviceApp() {
  return (
    <QueryClientProvider client={queryClient}>
      <Device />
    </QueryClientProvider>
  )
}

function StoredCover({ book }: { book: DeviceBook }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let url: string | null = null
    let live = true
    void deviceCover(book).then((u) => {
      url = u
      if (live) setSrc(u)
      else if (u) URL.revokeObjectURL(u)
    })
    return () => {
      live = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [book])
  return (
    <div
      className="relative w-14 shrink-0 overflow-hidden rounded-md bg-muted ring-1 ring-foreground/5"
      style={{ aspectRatio: '2 / 3' }}
    >
      {src && (
        <img
          src={src}
          alt=""
          className="absolute inset-0 size-full object-cover"
        />
      )}
    </div>
  )
}

function Row({ book, libraryName }: { book: DeviceBook; libraryName: string }) {
  const [busy, setBusy] = useState(false)
  const remove = async () => {
    if (!confirm(`Remove “${book.title}” from this device?`)) return
    setBusy(true)
    try {
      await removeDeviceBook(book)
    } finally {
      setBusy(false)
      void refreshDeviceBooks()
    }
  }
  return (
    <li className="flex items-center gap-4 py-3">
      <StoredCover book={book} />
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{book.title}</p>
        {book.authors.length > 0 && (
          <p className="truncate text-sm text-muted-foreground">
            {book.authors.join(', ')}
          </p>
        )}
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {[
            book.series && seriesText(book.series, book.series_index),
            libraryName,
            book.format,
            book.complete
              ? `Opened ${formatDate(book.opened.toISOString())}`
              : 'Not fully saved',
          ]
            .filter(Boolean)
            .join(' · ')}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Button asChild size="sm">
          <a href={readerUrl(book.library, book.id, book.format)}>
            <IconBook />
            Read
          </a>
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={() => void remove()}
          disabled={busy}
          aria-label={`Remove ${book.title} from this device`}
          title="Remove from this device"
        >
          <IconTrash />
        </Button>
      </div>
    </li>
  )
}

function Device() {
  const device = useDeviceBooks()
  const server = useServerInfo()
  const names = server.data?.library_map ?? {}
  const list = device.data ?? []

  useEffect(() => {
    document.title = 'On this device · Calibre Zen'
  }, [])

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 py-4 sm:px-6">
      <header className="flex items-center gap-2 pb-2">
        <Button
          asChild
          variant="ghost"
          size="icon"
          aria-label="Back to the library"
        >
          <a href={app()}>
            <IconArrowLeft />
          </a>
        </Button>
        <h1 className="text-lg font-semibold tracking-tight">On this device</h1>
      </header>
      <p className="pb-4 text-sm text-muted-foreground">
        Books you have opened in this browser. They open even with no
        connection.
      </p>

      {device.isPending ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : device.isError ? (
        <p className="text-sm text-muted-foreground">
          This browser&rsquo;s storage could not be read.
        </p>
      ) : list.length === 0 ? (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-muted-foreground">
            No books yet. A book you read here is kept for next time.
          </p>
          <Button asChild variant="outline" size="sm">
            <a href={app()}>Find a book</a>
          </Button>
        </div>
      ) : (
        <>
          <p className="pb-1 text-xs text-muted-foreground">
            {books(list.length)}
          </p>
          <ul className="divide-y" aria-label="Books on this device">
            {list.map((b) => (
              <Row
                key={`${b.library}/${b.id}/${b.format}`}
                book={b}
                libraryName={names[b.library] ?? b.library}
              />
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
