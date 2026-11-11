// The books calibre's reader keeps in this browser (lib/device.ts).
import { queryOptions, useSuspenseQuery } from '@tanstack/react-query'
import { deviceBooks } from '../device'
import { queryClient } from './client'
import { keys } from './keys'

export const deviceBooksQuery = () =>
  queryOptions({
    queryKey: keys.deviceBooks(),
    queryFn: deviceBooks,
    // It changes under us whenever the reader opens a book.
    staleTime: 0,
    refetchOnWindowFocus: true,
    retry: false,
    // The browser's own storage, so it is read with no network too.
    networkMode: 'always',
  })

/** The books stored in this browser, the most recently opened first. */
export function useDeviceBooks() {
  return useSuspenseQuery(deviceBooksQuery()).data
}

/** A book was stored or removed: read the list again. */
export function deviceBooksChanged() {
  return queryClient.invalidateQueries({ queryKey: keys.deviceBooks() })
}
