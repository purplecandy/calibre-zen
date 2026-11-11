// The library with no network: the last list and the books opened from it,
// kept in IndexedDB and put back into TanStack Query's cache when a page
// opens with no network. Covers are kept by the service worker
// (integrations/pwa.mjs).
//
// Only what the last list needs is kept, not every search ever typed: the
// server, each library's fields, the filters, the books opened, and the pages
// of whichever list was on screen. Only the library page writes the copy, so
// a visit to another page never drops the list from it. And it is only read
// with no network: online, every page asks the server as it always did, so
// what someone just changed is never shown as it was.
import { useSyncExternalStore } from 'react'
import { onlineManager, type Query } from '@tanstack/react-query'
import { createAsyncStoragePersister } from '@tanstack/query-async-storage-persister'
import {
  persistQueryClientRestore,
  persistQueryClientSubscribe,
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

/** Put the kept copy back, for a page opened with no network. */
export async function restore(): Promise<void> {
  try {
    await persistQueryClientRestore({ queryClient, ...persistOptions })
  } catch (e) {
    console.warn('The kept library could not be read:', e)
  }
}

/** Keep the cache from now on, as it changes. Returns a function to stop. */
export function keepForOffline(): () => void {
  return persistQueryClientSubscribe({ queryClient, ...persistOptions })
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
