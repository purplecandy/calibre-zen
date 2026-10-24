// The books calibre's reader keeps in this browser for reading offline.
//
// The reader stores every book it opens in an IndexedDB database of its own,
// `calibre`, at the same origin as this app (src/pyj/read_book/db.pyj). This
// reads that database as it is, and removes from it the way the reader
// does. It never creates it: a browser that has never opened a book has no
// such database, and an empty one made here would stop calibre's reader
// from setting it up.

const DB_NAME = 'calibre'
const DB_VERSION = 1

/** One book as the reader stores it. Only the parts this app reads. */
interface StoredBook {
  key: [string, number, string] // library, book id, format
  is_complete: boolean
  book_hash: string | null
  cover_name: string | null
  recent_date: Date
  metadata: {
    title?: string
    authors?: string[]
    series?: string
    series_index?: number
  }
  stored_files: Record<string, { encoded?: boolean; mimetype?: string }>
}

export interface DeviceBook {
  library: string
  id: number
  format: string
  title: string
  authors: string[]
  series?: string
  series_index?: number
  /** When it was last opened in this browser. */
  opened: Date
  /** Whether all of it is stored, so it opens with no network. */
  complete: boolean
  stored: StoredBook
}

function idb(): IDBFactory | undefined {
  return typeof indexedDB === 'undefined' ? undefined : indexedDB
}

/** Whether the reader's database exists, where the browser can say. */
async function exists(): Promise<boolean> {
  const f = idb()
  if (!f) return false
  if (typeof f.databases !== 'function') return true // asked below instead
  try {
    return (await f.databases()).some((d) => d.name === DB_NAME)
  } catch {
    return true
  }
}

/**
 * The reader's database, or null when there is none. Where the browser
 * cannot list its databases, an open that would create it is abandoned.
 */
async function open(): Promise<IDBDatabase | null> {
  const f = idb()
  if (!f || !(await exists())) return null
  return new Promise((resolve, reject) => {
    let created = false
    const req = f.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      // There was no database. Abort, so none is left behind for the
      // reader to trip over.
      created = true
      req.transaction?.abort()
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => {
      if (created) {
        f.deleteDatabase(DB_NAME)
        resolve(null)
      } else reject(req.error)
    }
    // The reader is upgrading it in another tab: try again later.
    req.onblocked = () => resolve(null)
  })
}

function done<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function toDeviceBook(b: StoredBook): DeviceBook {
  const m = b.metadata ?? {}
  return {
    library: b.key[0],
    id: Number(b.key[1]),
    format: String(b.key[2]).toUpperCase(),
    title: m.title || 'Unknown',
    authors: m.authors ?? [],
    series: m.series,
    series_index: m.series_index,
    opened: new Date(b.recent_date),
    complete: !!b.is_complete,
    stored: b,
  }
}

/** Every book stored in this browser, the last opened first. */
export async function deviceBooks(): Promise<DeviceBook[]> {
  const db = await open()
  if (!db) return []
  try {
    if (!db.objectStoreNames.contains('books')) return []
    const all = await done(
      db.transaction('books', 'readonly').objectStore('books').getAll(),
    )
    return (all as StoredBook[])
      .map(toDeviceBook)
      .sort((a, b) => b.opened.getTime() - a.opened.getTime())
  } finally {
    db.close()
  }
}

function fileKey(b: StoredBook, name: string): string {
  return `${b.book_hash} ${name}`
}

/** The cover the reader stored with a book, as a URL to revoke later. */
export async function deviceCover(book: DeviceBook): Promise<string | null> {
  const b = book.stored
  if (!b.book_hash || !b.cover_name) return null
  const db = await open()
  if (!db) return null
  try {
    const key = fileKey(b, b.cover_name)
    const data: unknown = await done(
      db.transaction('files', 'readonly').objectStore('files').get(key),
    )
    if (!data) return null
    const info = b.stored_files[key] ?? {}
    const type = info.mimetype || 'image/jpeg'
    let blob: Blob
    if (data instanceof Blob) blob = data
    else if (info.encoded && typeof data === 'string')
      blob = new Blob([Uint8Array.from(atob(data), (c) => c.charCodeAt(0))], {
        type,
      })
    else blob = new Blob([data as BlobPart], { type })
    return URL.createObjectURL(blob)
  } catch {
    return null
  } finally {
    db.close()
  }
}

/** Remove a book from this browser: its files, then its record, as the reader does. */
export async function removeDeviceBook(book: DeviceBook): Promise<void> {
  const db = await open()
  if (!db) return
  try {
    const t = db.transaction(['books', 'files'], 'readwrite')
    const files = t.objectStore('files')
    for (const name of Object.keys(book.stored.stored_files ?? {}))
      files.delete(name)
    t.objectStore('books').delete(book.stored.key)
    await new Promise<void>((resolve, reject) => {
      t.oncomplete = () => resolve()
      t.onerror = () => reject(t.error)
      t.onabort = () => reject(t.error)
    })
  } finally {
    db.close()
  }
}
