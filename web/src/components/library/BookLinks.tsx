// More for a book from its details: convert it to another format, and look
// it or its author up on the internet, as calibre's own book details offer.
// Beside components/edit/BookActions, which changes the book.
import {
  IconExternalLink,
  IconTransform,
  IconWorldSearch,
} from '@tabler/icons-react'
import type { Book } from '@/lib/api'
import { app } from '@/lib/base'
import { useOnline } from '@/lib/offline'
import { useServerInfo } from '@/lib/queries'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

// calibre's own list (src/pyj/book_list/book_details.pyj, search_internet).
const AUTHOR_SITES: [string, string][] = [
  ['Goodreads', 'https://www.goodreads.com/book/author/{author}'],
  ['Wikipedia', 'https://en.wikipedia.org/w/index.php?search={author}'],
  [
    'Google Books',
    'https://www.google.com/search?tbm=bks&q=inauthor:%22{author}%22',
  ],
]
const BOOK_SITES: [string, string][] = [
  [
    'Goodreads',
    'https://www.goodreads.com/search?q={author}+{title}&search%5Bsource%5D=goodreads&search_type=books&tab=books',
  ],
  [
    'Google Books',
    'https://www.google.com/search?tbm=bks&q=inauthor:%22{author}%22+intitle:%22{title}%22',
  ],
  [
    'Amazon',
    'https://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Dstripbooks&field-keywords={author}+{title}',
  ],
]

function fill(template: string, title: string, author: string): string {
  const enc = (s: string) => encodeURIComponent(s).replace(/%20/g, '+')
  return template
    .replace(/\{title\}/g, enc(title))
    .replace(/\{author\}/g, enc(author))
}

export function BookLinks({
  library,
  book,
}: {
  library: string
  book: Book & { id: number }
}) {
  const online = useOnline()
  const extra = useServerInfo().data?.search_the_net_urls ?? []
  const authorSites = [
    ...extra.filter((e) => e.type !== 'book').map((e) => [e.name, e.url]),
    ...AUTHOR_SITES,
  ]
  const bookSites = [
    ...extra.filter((e) => e.type === 'book').map((e) => [e.name, e.url]),
    ...BOOK_SITES,
  ]
  const author = book.authors?.[0] ?? ''
  const convert = app(
    `convert/?library=${encodeURIComponent(library)}&id=${book.id}`,
  )
  return (
    <section aria-label="More" className="flex flex-wrap gap-2">
      {online && (book.formats?.length ?? 0) > 0 ? (
        <Button asChild size="sm" variant="outline">
          <a href={convert}>
            <IconTransform />
            Convert
          </a>
        </Button>
      ) : (
        <Button size="sm" variant="outline" disabled>
          <IconTransform />
          Convert
        </Button>
      )}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm" variant="outline">
            <IconWorldSearch />
            Search the internet
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          {author && (
            <>
              <DropdownMenuLabel className="truncate text-xs font-normal text-muted-foreground">
                {author}
              </DropdownMenuLabel>
              {authorSites.map(([name, url]) => (
                <DropdownMenuItem key={'a' + name} asChild>
                  <a
                    href={fill(url, book.title, author)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <IconExternalLink className="size-4 text-muted-foreground" />
                    {name}
                  </a>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
            </>
          )}
          <DropdownMenuLabel className="truncate text-xs font-normal text-muted-foreground">
            {book.title}
          </DropdownMenuLabel>
          {bookSites.map(([name, url]) => (
            <DropdownMenuItem key={'b' + name} asChild>
              <a
                href={fill(url, book.title, author)}
                target="_blank"
                rel="noopener noreferrer"
              >
                <IconExternalLink className="size-4 text-muted-foreground" />
                {name}
              </a>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </section>
  )
}
