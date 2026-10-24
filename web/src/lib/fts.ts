// Full-text search: calibre's /fts endpoints, which search the words inside
// the books rather than their titles and tags. A library has it once someone
// turns it on, and then calibre reads each book in the background.
import { qs, request, ServerError } from './api'
import { server } from './base'

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

async function send(path: string, body?: unknown): Promise<void> {
  const res = await fetch(server(path), {
    method: body === undefined ? 'GET' : 'POST',
    cache: 'no-store',
    credentials: 'same-origin',
    headers:
      body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new ServerError(res.status, await res.text())
}

/** Turn full-text search on for a library. calibre starts reading its books. */
export function enableFts(library: string): Promise<void> {
  return send('fts/indexing' + qs({ library_id: library }), true)
}

/** Turn it off. The index is thrown away, and turning it on reads every book again. */
export function disableFts(library: string): Promise<void> {
  return send('fts/disable' + qs({ library_id: library }))
}

/** Read every book again, or just one. */
export function reindex(library: string, id?: number): Promise<void> {
  return send(
    'fts/reindex' + qs({ library_id: library }),
    id === undefined ? 'all' : { [id]: [] },
  )
}

// }}}

/** What to tell someone when a search or a change fails. */
export function ftsProblem(e: unknown): string {
  if (e instanceof ServerError) {
    if (e.status === 403)
      return 'Your account can search this library but not change it.'
    if (e.status === 422)
      return 'This search could not be read. Check its quotes and brackets.'
    if (e.status === 412) return 'Full-text search is off for this library.'
    return e.message || `The server answered ${e.status}.`
  }
  return 'The server could not be reached.'
}
