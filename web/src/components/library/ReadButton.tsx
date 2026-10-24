// Read, for one book: the file calibre's app would pick, and the others
// in a menu beside it when there are more.
import { IconBook, IconChevronDown } from '@tabler/icons-react'
import type { Book } from '@/lib/api'
import { useServerInfo } from '@/lib/queries'
import { preferredFormat, readableFormats, readHref } from '@/lib/reader'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

function ReadLink({
  library,
  bookId,
  fmt,
  children,
  ...rest
}: {
  library: string
  bookId: number
  fmt: string
  children: React.ReactNode
} & React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  const { href, newTab } = readHref(library, bookId, fmt)
  return (
    <a
      href={href}
      {...(newTab ? { target: '_blank', rel: 'noopener' } : {})}
      {...rest}
    >
      {children}
    </a>
  )
}

export function ReadButton({
  library,
  book,
}: {
  library: string
  book: Book & { id: number }
}) {
  const server = useServerInfo()
  if (!server.data) return null
  const best = preferredFormat(book, server.data)
  if (!best) return null
  const others = readableFormats(book, server.data).filter((f) => f !== best)

  return (
    <div className="flex">
      <Button
        asChild
        size="sm"
        className={others.length ? 'rounded-r-none' : undefined}
      >
        <ReadLink
          library={library}
          bookId={book.id}
          fmt={best}
          data-testid="read"
          title={`Read the ${best}`}
        >
          <IconBook />
          Read
        </ReadLink>
      </Button>
      {others.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              size="sm"
              className="rounded-l-none border-l border-primary-foreground/20 px-1.5"
              aria-label="Read another format"
            >
              <IconChevronDown />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              Read as
            </DropdownMenuLabel>
            {others.map((fmt) => (
              <DropdownMenuItem key={fmt} asChild>
                <ReadLink library={library} bookId={book.id} fmt={fmt}>
                  {fmt}
                </ReadLink>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  )
}
