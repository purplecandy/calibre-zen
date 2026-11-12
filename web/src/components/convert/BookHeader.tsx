// The book being converted: its cover, title and authors.
import type { Book } from '@/lib/api'
import { authors } from '@/lib/format'
import { useBook } from '@/lib/queries'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Section } from '@/components/app/Section'
import { Cover } from '@/components/library/Cover'

export function BookHeader({
  id,
  title,
  authors: names,
}: {
  id: number
  title: string
  authors: string[]
}) {
  return (
    <div className="flex gap-4">
      <div className="w-16 shrink-0 sm:w-20">
        <Section
          size="inline"
          loading={
            <div
              className="rounded-md bg-muted"
              style={{ aspectRatio: '2 / 3' }}
            />
          }
        >
          <BookCover id={id} title={title} />
        </Section>
      </div>
      <div className="min-w-0">
        <h2 className="font-serif text-xl leading-tight font-medium">
          {title}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{authors(names)}</p>
      </div>
    </div>
  )
}

/** The book's cover, at the version its metadata names. */
function BookCover({ id, title }: { id: number; title: string }) {
  const { library } = useLibraryContext()
  // The book's metadata, for its cover's version, so the cover is kept for
  // offline under an address that changes with it.
  const meta = useBook(library, id)
  const book: Book & { id: number } = {
    id,
    title,
    last_modified: meta.last_modified,
  }
  return <Cover book={book} width={80} eager />
}
