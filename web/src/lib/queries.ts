// The server's data, cached and shared: TanStack Query over lib/api.ts.
import {
  keepPreviousData,
  QueryClient,
  useQueries,
  useQuery,
} from '@tanstack/react-query'
import {
  bookMetadata,
  booksPage,
  browseField,
  libraryInfo,
  serverInfo,
  ServerError,
  type Book,
  type BookQuery,
} from './api'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 30 * 60_000,
      refetchOnWindowFocus: false,
      // A 401 is the browser asking for the login, and a 404 will not get
      // better. Anything else gets one more try.
      retry: (n, e) => n < 1 && !(e instanceof ServerError && e.status < 500),
    },
  },
})

export function useServerInfo() {
  return useQuery({
    queryKey: ['server'],
    queryFn: serverInfo,
    staleTime: 5 * 60_000,
  })
}

export function useLibrary(library: string | undefined) {
  return useQuery({
    queryKey: ['library', library],
    queryFn: () => libraryInfo(library!),
    enabled: !!library,
    staleTime: 5 * 60_000,
  })
}

// Books, a page at a time {{{

/** Books are fetched in pages of this many, for whatever is on screen. */
export const PAGE = 100

function pageQuery(q: BookQuery, page: number) {
  return {
    queryKey: ['books', q, page],
    queryFn: () => booksPage(q, page * PAGE, PAGE),
  }
}

export interface BookList {
  /** How many books match, once the first page is in. */
  total: number | undefined
  /** The book at `index`, if its page is in. */
  at(index: number): (Book & { id: number }) | undefined
  /** Whether the list on screen is from an earlier search, still being replaced. */
  stale: boolean
  error: unknown
}

/**
 * The books for `q`, with the pages that cover `visible` (first and last
 * index on screen) fetched. The first page is always fetched: it carries the
 * count. While a new search loads, the previous one stays on screen.
 */
export function useBookList(
  q: BookQuery | null,
  visible: [number, number],
): BookList {
  const first = useQuery({
    ...pageQuery(q!, 0),
    enabled: !!q,
    placeholderData: keepPreviousData,
  })
  const total = first.data?.search_result.total_num
  const pages: number[] = []
  if (q && total) {
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
  const rest = useQueries({ queries: pages.map((p) => pageQuery(q!, p)) })

  const loaded = new Map<number, Awaited<ReturnType<typeof booksPage>>>()
  if (first.data) loaded.set(0, first.data)
  pages.forEach((p, i) => {
    const d = rest[i]?.data
    if (d) loaded.set(p, d)
  })

  return {
    total,
    stale: first.isPlaceholderData,
    error: first.error,
    at(index) {
      const page = loaded.get(Math.floor(index / PAGE))
      if (!page) return undefined
      const id = page.search_result.book_ids[index % PAGE]
      const book = id === undefined ? undefined : page.metadata[id]
      return book ? { ...book, id } : undefined
    },
  }
}

/** One book: from a page already in, or asked for on its own. */
export function useBook(library: string | undefined, id: number | null) {
  return useQuery({
    queryKey: ['book', library, id],
    queryFn: () => bookMetadata(library!, id!),
    enabled: !!library && !!id,
    initialData: () => {
      if (!library || !id) return undefined
      for (const [, page] of queryClient.getQueriesData<
        Awaited<ReturnType<typeof booksPage>>
      >({
        queryKey: ['books'],
      })) {
        const book = page?.metadata[id]
        if (book && page.search_result.library_id === library)
          return { ...book, id }
      }
      return undefined
    },
  })
}

// }}}

export function useBrowseField(
  library: string | undefined,
  field: string,
  vl: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ['browse', library, field, vl],
    queryFn: () => browseField(library!, field, vl),
    enabled: enabled && !!library,
    staleTime: 5 * 60_000,
  })
}
