// Editing's share of the cache: who may edit, suggestions for a field, and
// bringing the lists up to date after a change.
import { useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { Book } from './api'
import { canEdit, fieldNames, type NoEditReason } from './edit'
import { queryClient } from './queries'

const REASONS: Record<NoEditReason | 'offline', string> = {
  anonymous:
    'Editing needs a login. Whoever shares this library can turn one on in calibre’s sharing settings.',
  'read-only': 'Your account can browse this library but not change it.',
  restricted:
    'Your account sees only part of this library, so it can’t change it.',
  offline: 'You’re offline. Editing comes back with the connection.',
}

function onOnline(f: () => void) {
  window.addEventListener('online', f)
  window.addEventListener('offline', f)
  return () => {
    window.removeEventListener('online', f)
    window.removeEventListener('offline', f)
  }
}

export interface EditPermission {
  /** Known and yes. While it is being asked, false. */
  allowed: boolean
  /** Why not, in a sentence, once it is known. */
  reason: string
}

/** Whether this browser may change `library`, and if not, why. */
export function useCanEdit(library: string | undefined): EditPermission {
  const online = useSyncExternalStore(onOnline, () => navigator.onLine)
  const q = useQuery({
    queryKey: ['can-edit', library],
    queryFn: () => canEdit(library!),
    enabled: !!library,
    staleTime: 5 * 60_000,
  })
  if (!online) return { allowed: false, reason: REASONS.offline }
  if (!q.data) return { allowed: false, reason: '' }
  return {
    allowed: q.data.can_edit,
    reason: q.data.reason ? REASONS[q.data.reason] : '',
  }
}

/** Every value `field` has in the library, fetched the first time it is wanted. */
export function useFieldNames(
  library: string,
  field: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ['field-names', library, field],
    queryFn: () => fieldNames(library, field),
    enabled,
    staleTime: 5 * 60_000,
  })
}

/**
 * After a write: the books calibre sent back go straight into the cache, and
 * everything that counts or lists books is fetched again.
 */
export function afterWrite(
  library: string,
  changed: Record<string, Book> = {},
) {
  for (const [id, book] of Object.entries(changed)) {
    queryClient.setQueryData(['book', library, Number(id)], {
      ...book,
      id: Number(id),
    })
  }
  void queryClient.invalidateQueries({ queryKey: ['books'] })
  void queryClient.invalidateQueries({ queryKey: ['browse', library] })
  void queryClient.invalidateQueries({ queryKey: ['library', library] })
  void queryClient.invalidateQueries({ queryKey: ['field-names', library] })
}
