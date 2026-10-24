// calibre's own JSON endpoints, unchanged. A request that needs a login gets
// a 401 the first time, the browser asks for the username and password, and
// every request after it carries them -- the same as calibre's web app.
//
// The shapes below are the parts this app reads. calibre sends more.
import { server } from './base'

export class ServerError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(server(path), {
    credentials: 'same-origin',
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  })
  if (!res.ok) throw new ServerError(res.status, await res.text())
  return (await res.json()) as T
}

export function qs(
  params: Record<string, string | number | undefined>,
): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') q.set(k, String(v))
  }
  const s = q.toString()
  return s ? '?' + s : ''
}

// The server {{{

/** /interface-data/update: who is signed in, and which libraries there are. */
export interface ServerInfo {
  username: string | null
  library_map: Record<string, string>
  default_library_id: string
  num_per_page: number
  default_book_list_mode: string
  /** Sites the server's owner added to Search the internet. */
  search_the_net_urls?: { name: string; url: string; type: 'book' | 'author' }[]
}

export function serverInfo(): Promise<ServerInfo> {
  return request<ServerInfo>('interface-data/update')
}

// }}}

// A library {{{

export interface FieldMetadata {
  name: string
  datatype: string | null
  is_multiple?: {
    ui_to_list?: string
    list_to_ui?: string
    cache_to_list?: string
  }
  is_custom?: boolean
  is_category?: boolean
  kind?: string
  display?: Record<string, unknown>
  label?: string
}

export interface BrowseField {
  key: string
  name: string
  kind: 'category' | 'date'
  is_custom: boolean
  datatype: string
  default_visible: boolean
}

/** What stays the same while someone browses one library. */
export interface LibraryInfo {
  library_id: string
  sortable_fields: [string, string][]
  field_metadata: Record<string, FieldMetadata>
  virtual_libraries: Record<string, string>
  book_display_fields: string[]
  browse_fields: BrowseField[]
  fts_enabled: boolean
  num_books: number
}

interface BooksInit extends Omit<LibraryInfo, 'num_books'> {
  search_result: SearchResult
}

export async function libraryInfo(library: string): Promise<LibraryInfo> {
  // books-init with no books: the library's fields, sorts and virtual
  // libraries, without paying for a page of metadata.
  const d = await request<BooksInit>(
    'interface-data/books-init' + qs({ library_id: library, num: 0 }),
  )
  return {
    library_id: d.library_id,
    sortable_fields: d.sortable_fields,
    field_metadata: d.field_metadata,
    virtual_libraries: d.virtual_libraries ?? {},
    book_display_fields: d.book_display_fields,
    browse_fields: d.browse_fields ?? [],
    fts_enabled: d.fts_enabled,
    num_books: d.search_result.num_books_without_search,
  }
}

// }}}

// Books {{{

/** book_as_json: every field with a value, by its lookup name. */
export interface Book {
  id?: number
  title: string
  authors?: string[]
  author_sort?: string
  series?: string
  series_index?: number
  tags?: string[]
  rating?: number
  publisher?: string
  pubdate?: string
  timestamp?: string
  last_modified?: string
  languages?: string[]
  lang_names?: Record<string, string>
  comments?: string
  identifiers?: Record<string, string>
  urls_from_identifiers?: [string, string, string, string][]
  formats?: string[]
  format_sizes?: Record<string, number>
  [field: string]: unknown
}

export interface SearchResult {
  library_id: string
  total_num: number
  num_books_without_search: number
  offset: number
  num: number
  book_ids: number[]
  bad_restriction?: string
}

export interface BooksPage {
  search_result: SearchResult
  metadata: Record<string, Book>
}

export interface BookQuery {
  library: string
  search: string
  sort: string // field
  order: 'asc' | 'desc'
  vl: string
}

export function booksPage(
  q: BookQuery,
  offset: number,
  num: number,
): Promise<BooksPage> {
  return request<BooksPage>(
    'interface-data/more-books' + qs({ library_id: q.library, num }),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: q.search,
        offset,
        sort: q.sort,
        sort_order: q.order,
        vl: q.vl,
      }),
    },
  )
}

export function bookMetadata(library: string, id: number): Promise<Book> {
  return request<Book>(
    `interface-data/book-metadata/${id}` + qs({ library_id: library }),
  )
}

// }}}

// Filters {{{

export interface BrowseItem {
  name: string
  count: number
  avg_rating: number | null
  search: string
}

export function browseField(
  library: string,
  field: string,
  vl: string,
): Promise<BrowseItem[]> {
  return request<{ items: BrowseItem[] }>(
    `interface-data/browse-field/${encodeURIComponent(field)}` +
      qs({ library_id: library, vl }),
  ).then((d) => d.items)
}

// }}}

// Files {{{

// Cover widths the server is asked for, in device pixels. calibre scales and
// keeps a copy per size, so a few sizes shared by every layout and screen
// are made once and then come from its cache and the browser's.
const THUMB_WIDTHS = [96, 144, 192, 288, 384, 576]

/** A cover for `w` CSS pixels wide on this screen, at one of the shared sizes. */
export function thumbUrl(
  library: string,
  book: Book & { id: number },
  w: number,
) {
  const dpr = Math.min(window.devicePixelRatio || 1, 3)
  const want = Math.ceil(w * dpr)
  const width =
    THUMB_WIDTHS.find((x) => x >= want) ?? THUMB_WIDTHS[THUMB_WIDTHS.length - 1]
  return server(
    `get/thumb/${book.id}/${encodeURIComponent(library)}` +
      qs({
        sz: `${width}x${width * 1.5}`,
        // A new cover changes last_modified; the old one stays cached under
        // the old address.
        t: book.last_modified,
      }),
  )
}

export function coverUrl(library: string, book: Book & { id: number }) {
  return server(
    `get/cover/${book.id}/${encodeURIComponent(library)}` +
      qs({ t: book.last_modified }),
  )
}

export function downloadUrl(library: string, id: number, format: string) {
  return server(`get/${format}/${id}/${encodeURIComponent(library)}`)
}

// }}}
