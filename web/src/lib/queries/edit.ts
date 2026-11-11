// Editing's share of the cache: who may edit, the values a field already
// has for suggestions, and bringing the lists up to date after a change.
import { queryOptions, useQuery } from '@tanstack/react-query'
import type { Book } from '../api'
import { canEdit, fieldNames, type DataFiles, type NoEditReason } from '../edit'
import { useOnline } from '../hooks/useOnline'
import { queryClient } from './client'
import { keys } from './keys'

const REASONS: Record<NoEditReason | 'offline', string> = {
  anonymous:
    'Editing needs a login. Whoever shares this library can turn one on in calibre’s sharing settings.',
  'read-only': 'Your account can browse this library but not change it.',
  restricted:
    'Your account sees only part of this library, so it can’t change it.',
  offline: 'You’re offline. Editing comes back with the connection.',
}

export interface EditPermission {
  /** Known and yes. While it is being asked, false. */
  allowed: boolean
  /** Why not, in a sentence, once it is known. */
  reason: string
}

export const canEditQuery = (library: string) =>
  queryOptions({
    queryKey: keys.canEdit(library),
    queryFn: () => canEdit(library),
    staleTime: 5 * 60_000,
  })

/**
 * Whether this browser may change `library`, and if not, why.
 *
 * It does not suspend, on purpose. It only decides whether buttons are
 * there, "not yet known" means "not there", and offline it answers at once
 * without asking. Suspending would hold a book's details until it was in,
 * and forever with no network.
 */
export function useCanEdit(library: string): EditPermission {
  const online = useOnline()
  const q = useQuery(canEditQuery(library))
  if (!online) return { allowed: false, reason: REASONS.offline }
  if (!q.data) return { allowed: false, reason: '' }
  return {
    allowed: q.data.can_edit,
    reason: q.data.reason ? REASONS[q.data.reason] : '',
  }
}

export const fieldNamesQuery = (library: string, field: string) =>
  queryOptions({
    queryKey: keys.fieldNames.one(library, field),
    queryFn: () => fieldNames(library, field),
    staleTime: 5 * 60_000,
  })

/**
 * Every value `field` has in the library, fetched the first time it is
 * wanted. Suggestions for a text box: they never suspend, so the box is
 * never blanked while they load, and until they are in there are none.
 */
export function useFieldNames(
  library: string,
  field: string,
  enabled: boolean,
): readonly string[] {
  return useQuery({ ...fieldNamesQuery(library, field), enabled }).data ?? []
}

/**
 * After a change to `library`: the books calibre sent back go straight into
 * the cache, and everything that counts or lists books is fetched again.
 */
export function booksChanged(
  library: string,
  changed: Record<string, Book> = {},
) {
  for (const [id, book] of Object.entries(changed)) {
    queryClient.setQueryData(keys.book.one(library, Number(id)), {
      ...book,
      id: Number(id),
    })
  }
  void queryClient.invalidateQueries({ queryKey: keys.books.all() })
  void queryClient.invalidateQueries({ queryKey: keys.browse.all(library) })
  void queryClient.invalidateQueries({ queryKey: keys.library(library) })
  void queryClient.invalidateQueries({
    queryKey: keys.fieldNames.all(library),
  })
}

/** A book's data files changed: its cached details take the new list. */
export function dataFilesChanged(
  library: string,
  id: number,
  data_files: DataFiles,
) {
  queryClient.setQueryData(
    keys.book.one(library, id),
    (old) => old && { ...old, data_files },
  )
}
