// What someone has been reading: the server's list when they are signed in,
// which follows them across devices, and the books this browser has opened,
// which is all there is without a login.
import { sortBy, uniqueBy } from 'remeda'
import type { DeviceBook } from './device'
import { useDeviceBooks, useServerInfo } from './queries'

export interface ReadingItem {
  library: string
  id: number
  format: string
  title: string
  /** 0 to 1, when the server knows it. */
  progress?: number
  when: Date
}

/**
 * Recently read books, the most recent first, one entry per book. Suspends
 * until the server and this browser's storage have both answered.
 */
export function useRecentlyRead(limit = 5): ReadingItem[] {
  const server = useServerInfo()
  const device = useDeviceBooks()
  const libraries = server.library_map

  const fromServer = (server.recently_read_by_user ?? []).map(
    (r): ReadingItem => ({
      library: r.library_id,
      id: r.book_id,
      format: r.format.toUpperCase(),
      // The server keeps "Title by Author"; the title is what fits.
      title: r.tooltip,
      progress: r.pos_frac,
      // calibre keeps the time in nanoseconds.
      when: new Date(r.epoch / 1e6),
    }),
  )
  const fromDevice = device.map((b: DeviceBook): ReadingItem => ({
    library: b.library,
    id: b.id,
    format: b.format,
    title: b.title,
    when: b.opened,
  }))
  // A book in both lists takes its place from the later of the two, and its
  // entry from the server, which has the progress.
  const byTime = sortBy(
    [...fromServer, ...fromDevice],
    [(item) => item.when.getTime(), 'desc'],
  )
  const items = byTime
    .map(
      (item) =>
        fromServer.find(
          (s) => s.library === item.library && s.id === item.id,
        ) ?? item,
    )
    .filter((item) => Object.hasOwn(libraries, item.library))
  return uniqueBy(items, (item) => `${item.library}/${item.id}`).slice(0, limit)
}
