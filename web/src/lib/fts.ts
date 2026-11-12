// Full-text search: calibre's /fts endpoints, which search the words inside
// the books rather than their titles and tags. A library has it once someone
// turns it on, and then calibre reads each book in the background.
import { serverSaid, UNREACHABLE, type Wording } from './errors'
import { post, qs, request, type RequestOptions } from './http'

export interface FtsQuery {
  library: string
  query: string
  /** Also match other forms of each word: read finds reading. */
  related: boolean
  /** A calibre search that limits which books are searched. */
  restrict: string
}

export interface FtsResults {
  /** Each book's title and authors, by id. */
  metadata: Record<string, { title: string; authors: string }>
  indexing_status: { left: number; total: number }
  /** One per book and format the words were found in. */
  results: { book_id: number; format: string }[]
}

export function ftsSearch(q: FtsQuery): Promise<FtsResults> {
  return request<FtsResults>(
    'fts/search' +
      qs({
        library_id: q.library,
        query: q.query,
        use_stemming: q.related ? 'y' : 'n',
        restriction: q.restrict || undefined,
      }),
  )
}

export interface Snippet {
  formats: string[]
  /** The text around a match, each match between \x1c and \x1e. */
  text: string
}

export function ftsSnippets(
  q: FtsQuery,
  ids: number[],
): Promise<Record<string, Snippet[]>> {
  return request<{ snippets: Record<string, Snippet[]> }>(
    `fts/snippets/${ids.join(',')}` +
      qs({
        library_id: q.library,
        query: q.query,
        use_stemming: q.related ? 'y' : 'n',
      }),
  ).then((d) => d.snippets)
}

/** The parts of a snippet: plain text, and the words that matched. */
export function snippetParts(text: string): { match: boolean; text: string }[] {
  const parts: { match: boolean; text: string }[] = []
  const clean = text.replace(/\s+/g, ' ').trim()
  const re = /\x1c([^\x1e]*)\x1e/g
  let last = 0
  for (let m = re.exec(clean); m; m = re.exec(clean)) {
    if (m.index > last)
      parts.push({ match: false, text: clean.slice(last, m.index) })
    parts.push({ match: true, text: m[1] })
    last = m.index + m[0].length
  }
  if (last < clean.length) parts.push({ match: false, text: clean.slice(last) })
  return parts
}

// Changing the index {{{

// Never from the browser's cache, and nothing to read in the answer.
const CHANGE: RequestOptions = { cache: 'no-store', as: 'none' }

/** Turn full-text search on for a library. calibre starts reading its books. */
export function enableFts(library: string): Promise<void> {
  return post('fts/indexing' + qs({ library_id: library }), true, CHANGE)
}

/** Turn it off. The index is thrown away, and turning it on reads every book again. */
export function disableFts(library: string): Promise<void> {
  return request('fts/disable' + qs({ library_id: library }), CHANGE)
}

/** Read every book again, or just one. */
export function reindex(library: string, id?: number): Promise<void> {
  return post(
    'fts/reindex' + qs({ library_id: library }),
    id === undefined ? 'all' : { [id]: [] },
    CHANGE,
  )
}

// }}}

/** What to tell someone when a search or a change fails. */
export const FTS_ERRORS: Wording = {
  status: {
    403: 'Your account can search this library but not change it.',
    422: 'This search could not be read. Check its quotes and brackets.',
    412: 'Full-text search is off for this library.',
  },
  server: serverSaid,
  other: UNREACHABLE,
}
