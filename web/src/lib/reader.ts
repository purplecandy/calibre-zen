// Reading a book, in calibre's own reader for now (docs/plans/web/, "The
// reader"). The reader lives in calibre's app at the server's root and opens
// from its address: same origin, so it finds the books it already keeps for
// offline reading, and its Back comes back here.
import type { Book, ServerInfo } from './api'
import { downloadUrl } from './api'
import { server } from './base'

// calibre's order for picking a book's file to read, from
// src/pyj/book_list/book_details.pyj.
const FORMAT_PRIORITIES = [
  'EPUB',
  'AZW3',
  'DOCX',
  'LIT',
  'MOBI',
  'ODT',
  'RTF',
  'MD',
  'MARKDOWN',
  'TXT',
  'PDF',
]

function priority(fmt: string): number {
  const i = FORMAT_PRIORITIES.indexOf(fmt)
  return i < 0 ? FORMAT_PRIORITIES.length : i
}

type Formats = Pick<ServerInfo, 'input_formats' | 'output_format'>

/**
 * The files of `book` the reader can open, best first. The server converts
 * anything it can take as input, so that is what calibre's app offers too.
 */
export function readableFormats(book: Book, s: Formats): string[] {
  const inputs = s.input_formats ?? {}
  return (book.formats ?? [])
    .map((f) => f.toUpperCase())
    .filter((f) => inputs[f])
    .sort((a, b) => priority(a) - priority(b))
}

/**
 * The file Read opens: the one calibre's app would pick, which is the
 * library's output format when the book has it, and the best of the rest
 * otherwise. Undefined when there is nothing to read.
 */
export function preferredFormat(book: Book, s: Formats): string | undefined {
  const formats = readableFormats(book, s)
  const out = (s.output_format ?? 'EPUB').toUpperCase()
  const want = out === 'PDF' ? 'EPUB' : out
  return formats.includes(want) ? want : formats[0]
}

/** Where calibre's reader opens this book, in this format. */
export function readerUrl(library: string, id: number, fmt: string): string {
  // The same keys, in the same sorted order, that calibre's
  // open_book_url_in_library writes.
  const q: Record<string, string> = {
    book_id: String(id),
    fmt,
    library_id: library,
    mode: 'read_book',
  }
  const hash = Object.keys(q)
    .sort()
    .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(q[k])}`)
    .join('&')
  return server('') + '#' + hash
}

/**
 * Where Read goes. calibre's reader does not lay out PDFs; its app opens them
 * in the browser instead, and so does this.
 */
export function readHref(
  library: string,
  id: number,
  fmt: string,
): { href: string; newTab: boolean } {
  if (fmt === 'PDF')
    return {
      href: downloadUrl(library, id, fmt) + '?content_disposition=inline',
      newTab: true,
    }
  return { href: readerUrl(library, id, fmt), newTab: false }
}
