// The note on one author, series, tag and so on. calibre keeps one note per
// item, shared by every book that has it.
import { queryOptions, useSuspenseQuery } from '@tanstack/react-query'
import { getNote } from '../edit'
import { queryClient } from './client'
import { keys } from './keys'

export const noteQuery = (library: string, field: string, value: string) =>
  queryOptions({
    queryKey: keys.note(library, field, value),
    queryFn: () => getNote(library, field, value),
  })

/** The note on `value` of `field`: its item id and HTML, '' for none. */
export function useNote(library: string, field: string, value: string) {
  return useSuspenseQuery(noteQuery(library, field, value)).data
}

/**
 * A note was saved: it takes its new HTML at once, and the book that showed
 * it is fetched again, for which of its items have notes.
 */
export function noteChanged(
  library: string,
  field: string,
  value: string,
  bookId: number,
  html: string,
) {
  queryClient.setQueryData(
    keys.note(library, field, value),
    (old) => old && { ...old, html },
  )
  void queryClient.invalidateQueries({
    queryKey: keys.book.one(library, bookId),
  })
}
