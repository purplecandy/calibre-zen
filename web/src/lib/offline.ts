// The library with no network: the last list and the books opened from it,
// kept in IndexedDB and put back into TanStack Query's cache when a page
// opens. Covers are kept by the service worker (integrations/pwa.mjs).
//
// Only what the last list needs is kept, not every search ever typed: the
// server, each library's fields, the filters, the books opened, and the pages
// of whichever list was on screen.
import { useSyncExternalStore } from 'react'
import { onlineManager, type Query } from '@tanstack/react-query'
import { createAsyncStoragePersister } from '@tanstack/query-async-storage-persister'
import {
  persistQueryClientSave,
  type PersistQueryClientOptions,
} from '@tanstack/react-query-persist-client'
import { del, get, set } from 'idb-keyval'
import { SERVER_URL } from './base'
import { queryClient } from './queries'

// TanStack Query starts out believing it is online. A page opened with no
// network would then try every request and show the failures, rather than
// pausing them and showing what it kept.
onlineManager.setOnline(navigator.onLine)

const KEPT = new Set(['server', 'library', 'book', 'browse', 'books'])

function keep(query: Query): boolean {
  if (query.state.status !== 'success') return false
  const kind = query.queryKey[0] as string
  if (!KEPT.has(kind)) return false
  // Pages of a list are kept while they are on screen, so what is kept is
  // the list someone was last looking at.
  return kind !== 'books' || query.getObserversCount() > 0
}

/** Change it when what is kept changes shape, and old copies are dropped. */
const VERSION = 'zen-1'

export const persistOptions: Omit<PersistQueryClientOptions, 'queryClient'> = {
  persister: createAsyncStoragePersister({
    storage: { getItem: get, setItem: set, removeItem: del },
    // One copy per server: /books/app/ and /app/ on one host are two.
    key: 'zen-library:' + SERVER_URL,
    throttleTime: 2000,
  }),
  maxAge: 30 * 24 * 60 * 60_000,
  buster: VERSION,
  dehydrateOptions: { shouldDehydrateQuery: keep },
}

/**
 * Write what is kept now, not a moment from now. For a change made just
 * before going to another page, which reads the kept copy when it opens.
 */
export function saveNow(): Promise<void> {
  return persistQueryClientSave({ queryClient, ...persistOptions })
}

function isOnline() {
  return onlineManager.isOnline()
}

/** Whether the browser has a network. Anything that changes the library is off without one. */
export function useOnline(): boolean {
  return useSyncExternalStore(
    onlineManager.subscribe.bind(onlineManager),
    isOnline,
  )
}
