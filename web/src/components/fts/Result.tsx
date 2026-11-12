// One book a search found: its cover, title and authors, the formats the
// words were in, and up to three passages with the words picked out.
import type { ReactNode } from 'react'
import type { Book } from '@/lib/api'
import { snippetParts } from '@/lib/model/fts'
import { bookLink } from '@/lib/url'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Cover } from '@/components/library/Cover'
import { ResultMenu } from './ResultMenu'

export function Result({
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
