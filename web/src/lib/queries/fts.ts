// Full-text search: the books whose words match, the passages around the
// matches, and bringing both up to date when the index changes.
import { queryOptions, useSuspenseQuery } from '@tanstack/react-query'
import { ftsSearch, ftsSnippets, type FtsQuery } from '../fts'
import { queryClient } from './client'
import { keys } from './keys'

export const ftsSearchQuery = (query: FtsQuery) =>
  queryOptions({
    queryKey: keys.fts.search(query),
    queryFn: () => ftsSearch(query),
    // While calibre is still reading books, new matches turn up.
    refetchInterval: (q) =>
      (q.state.data?.indexing_status.left ?? 0) > 0 ? 5000 : false,
  })

/** The books that contain the words, and how far calibre has read. */
export function useFtsSearch(query: FtsQuery) {
  return useSuspenseQuery(ftsSearchQuery(query)).data
}

export const ftsSnippetsQuery = (query: FtsQuery, ids: readonly number[]) =>
  queryOptions({
    queryKey: keys.fts.snippets(query, ids),
    queryFn: () => ftsSnippets(query, [...ids]),
    staleTime: Infinity,
  })

/** The passages that matched, for a batch of books, by book id. */
export function useFtsSnippets(query: FtsQuery, ids: readonly number[]) {
  return useSuspenseQuery(ftsSnippetsQuery(query, ids)).data
}

/** Full-text search was turned on: the library says so once this resolves. */
export function ftsTurnedOn(library: string) {
  return queryClient.invalidateQueries({ queryKey: keys.library(library) })
}

/** The index was read again or thrown away: the library and every search. */
export function ftsChanged(library: string) {
  void queryClient.invalidateQueries({ queryKey: keys.library(library) })
  void queryClient.invalidateQueries({ queryKey: keys.fts.all() })
}
