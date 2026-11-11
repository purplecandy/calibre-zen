// The library's reads: the server, a library, its books a page at a time, one
// book, and the values of a field for the sidebar. Each hook suspends until
// its data is in and returns the data itself, so it is used inside a
// <Section> (components/app/Section.tsx), which shows loading and failure.
import {
  queryOptions,
  useQueries,
  useSuspenseQuery,
} from '@tanstack/react-query'
import {
  bookMetadata,
  booksPage,
  browseField,
  libraryInfo,
  serverInfo,
  type Book,
  type BookQuery,
} from '../api'
import { queryClient } from './client'
import { keys } from './keys'

export const serverQuery = () =>
  queryOptions({
    queryKey: keys.server(),
    queryFn: serverInfo,
    staleTime: 5 * 60_000,
  })

/** The server: its libraries, the default one, who is signed in. */
export function useServerInfo() {
  return useSuspenseQuery(serverQuery()).data
}

export const libraryQuery = (library: string) =>
  queryOptions({
    queryKey: keys.library(library),
    queryFn: () => libraryInfo(library),
    staleTime: 5 * 60_000,
  })

/** One library's fields, virtual libraries and sorts. */
export function useLibrary(library: string) {
  return useSuspenseQuery(libraryQuery(library)).data
}

// Books, a page at a time {{{

/** Books are fetched in pages of this many, for whatever is on screen. */
export const PAGE = 100

type Page = Awaited<ReturnType<typeof booksPage>>

export const booksPageQuery = (q: BookQuery, page: number) =>
  queryOptions({
    queryKey: keys.books.page(q, page),
    queryFn: () => booksPage(q, page * PAGE, PAGE),
  })

export interface BookList {
  /** How many books match. */
  total: number
  /** The book at `index`, if its page is in. */
  at(index: number): (Book & { id: number }) | undefined
}

/**
 * The books for `q`, with the pages that cover `visible` (first and last
 * index on screen) fetched. The first page carries the count, so it
 * suspends; the rest fill in as they arrive and never blank the list.
 *
 * Pass `q` built from a deferred view (useDeferredValue), so a new search
 * keeps the old list on screen while it loads instead of suspending.
 */
export function useBookList(q: BookQuery, visible: [number, number]): BookList {
  const first = useSuspenseQuery(booksPageQuery(q, 0)).data
  const total = first.search_result.total_num
  const pages: number[] = []
  if (total) {
    const last = Math.min(
      Math.floor(Math.max(visible[1], 0) / PAGE),
      Math.floor((total - 1) / PAGE),
    )
    for (
      let p = Math.max(1, Math.floor(Math.max(visible[0], 0) / PAGE));
      p <= last;
      p++
    ) {
      pages.push(p)
    }
  }
  const rest = useQueries({
    queries: pages.map((p) => booksPageQuery(q, p)),
  })

  const loaded = new Map<number, Page>([[0, first]])
  pages.forEach((p, i) => {
    const d = rest[i]?.data
    if (d) loaded.set(p, d)
  })

  return {
    total,
    at(index) {
      const page = loaded.get(Math.floor(index / PAGE))
      if (!page) return undefined
      const id = page.search_result.book_ids[index % PAGE]
      const book = id === undefined ? undefined : page.metadata[id]
      return book ? { ...book, id } : undefined
    },
  }
}

/** A book already in a page of a list, so its details open at once. */
function fromLists(library: string, id: number) {
  for (const [, page] of queryClient.getQueriesData<Page>({
    queryKey: keys.books.all(),
  })) {
    const book = page?.metadata[id]
    if (book && page.search_result.library_id === library)
      return { ...book, id }
  }
  return undefined
}

export const bookQuery = (library: string, id: number) =>
  queryOptions({
    queryKey: keys.book.one(library, id),
    queryFn: async () => ({ ...(await bookMetadata(library, id)), id }),
    initialData: () => fromLists(library, id),
  })

/** One book: from a page already in, or asked for on its own. */
export function useBook(library: string, id: number) {
  return useSuspenseQuery(bookQuery(library, id)).data
}

// }}}

export const browseQuery = (library: string, field: string, vl: string) =>
  queryOptions({
    queryKey: keys.browse.field(library, field, vl),
    queryFn: () => browseField(library, field, vl),
    staleTime: 5 * 60_000,
  })

/** Every value of `field` in the library or virtual library, with counts. */
export function useBrowseField(library: string, field: string, vl: string) {
  return useSuspenseQuery(browseQuery(library, field, vl)).data
}
