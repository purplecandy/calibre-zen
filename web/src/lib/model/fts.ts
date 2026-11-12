// Full-text search results, as the page shows them: one result per book,
// in batches that fetch their passages when shown, and each passage with the
// words that matched picked out.
import { chunk } from 'remeda'
import type { FtsResults } from '@/lib/fts'

/** Each book the words were found in, with the formats they were found in. */
export function formatsByBook(
  results: FtsResults['results'],
): Map<number, string[]> {
  const byBook = new Map<number, string[]>()
  for (const r of results)
    byBook.set(r.book_id, [...(byBook.get(r.book_id) ?? []), r.format])
  return byBook
}

/** The first `shown` of `ids`, in batches of `size`. */
export function batches(
  ids: number[],
  shown: number,
  size: number,
): number[][] {
  return chunk(ids.slice(0, shown), size)
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
