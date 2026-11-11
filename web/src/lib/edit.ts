// Changing the library: calibre's own write endpoints, unchanged, plus
// /zen/api/can-edit, which says up front whether they will say yes
// (src/calibre_zen/web/access.py). The shapes are the parts this app reads.
import { server } from './base'
import { post, qs, request, ServerError } from './http'
import type { Book } from './api'

const lib = (library: string) => encodeURIComponent(library)

// Who may edit {{{

export type NoEditReason = 'anonymous' | 'read-only' | 'restricted'

export interface EditAccess {
  can_edit: boolean
  reason: NoEditReason | ''
}

export async function canEdit(library: string): Promise<EditAccess> {
  try {
    return await request<EditAccess>(
      'zen/api/can-edit' + qs({ library_id: library }),
    )
  } catch (e) {
    // A server without zen's API: calibre's app shows every control and
    // lets the server decide, so this does the same.
    if (e instanceof ServerError && e.status === 404)
      return { can_edit: true, reason: '' }
    throw e
  }
}

// }}}

// Metadata and cover {{{

/** What a field is sent to set-fields as. */
export type FieldValue =
  string | number | boolean | null | string[] | Record<string, string>

export interface AddedFormat {
  ext: string
  data_url: string
}

/** Every book set-fields changed, as book_as_json, keyed by id. */
export function setFields(
  library: string,
  id: number,
  changes: Record<string, unknown>,
): Promise<Record<string, Book>> {
  return post(`cdb/set-fields/${id}/${lib(library)}`, {
    changes,
    loaded_book_ids: [id],
  })
}

/**
 * A picture as set-fields takes a cover: a data: URL of a JPEG or PNG, which
 * is all calibre accepts there. Anything else the browser can show is drawn
 * once and sent as a JPEG.
 */
export async function coverDataUrl(file: Blob): Promise<string> {
  if (file.type === 'image/jpeg' || file.type === 'image/png') {
    return readAsDataUrl(file)
  }
  const bitmap = await createImageBitmap(file)
  const canvas = document.createElement('canvas')
  canvas.width = bitmap.width
  canvas.height = bitmap.height
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0)
  bitmap.close()
  return canvas.toDataURL('image/jpeg', 0.92)
}

/** All the values a field has in the library, for suggestions. */
export function fieldNames(library: string, field: string): Promise<string[]> {
  return request<string[]>(
    `interface-data/field-names/${encodeURIComponent(field)}` +
      qs({ library_id: library }),
  )
}

// }}}

// Adding, deleting and copying {{{

export interface AddResult {
  id: string
  filename: string
  title: string
  authors: string[]
  book_id?: number
  duplicates?: { title: string; authors: string[] }[]
}

/**
 * Upload one book file. XHR rather than fetch, for the upload's progress.
 * `duplicates` decides whether a book calibre thinks is already there is
 * added anyway.
 */
export function addBook(
  library: string,
  file: File,
  job: number,
  duplicates: boolean,
  onProgress: (fraction: number) => void,
): { promise: Promise<AddResult>; abort: () => void } {
  const xhr = new XMLHttpRequest()
  const promise = new Promise<AddResult>((resolve, reject) => {
    xhr.open(
      'POST',
      server(
        `cdb/add-book/${job}/${duplicates ? 'y' : 'n'}/${encodeURIComponent(file.name)}/${lib(library)}`,
      ),
    )
    xhr.withCredentials = true
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total)
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as AddResult)
        } catch (e) {
          reject(e)
        }
      } else {
        reject(new ServerError(xhr.status, xhr.responseText))
      }
    }
    xhr.onerror = () => reject(new ServerError(0, 'The upload stopped.'))
    xhr.onabort = () => reject(new DOMException('Cancelled', 'AbortError'))
    xhr.send(file)
  })
  return { promise, abort: () => xhr.abort() }
}

/** Into the library's trash, as calibre's own app does. */
export function deleteBooks(library: string, ids: number[]) {
  return post<object>(`cdb/delete-books/${ids.join(',')}/${lib(library)}`)
}

export type DuplicateAction = 'add' | 'ignore' | 'add_formats_to_existing'

export interface CopyResult {
  ok: boolean
  payload: { action: 'add' | 'duplicate' | 'automerge'; new_book_id?: number }
}

export function copyToLibrary(
  library: string,
  target: string,
  id: number,
  { move, duplicates }: { move: boolean; duplicates: DuplicateAction },
): Promise<CopyResult> {
  return post<Record<string, CopyResult>>(
    `cdb/copy-to-library/${lib(target)}/${lib(library)}`,
    {
      book_ids: [id],
      move,
      duplicate_action: duplicates,
      // Merging keeps the files that are there already.
      automerge_action: 'ignore',
    },
  ).then((r) => r[id])
}

// }}}

// Data files {{{

export type DataFiles = Record<string, { size: number; mtime_ns: number }>

export function dataFileUrl(library: string, id: number, relpath: string) {
  return server(
    `data-files/get/${id}/${encodeURIComponent(relpath)}/${lib(library)}`,
  )
}

export function uploadDataFiles(
  library: string,
  id: number,
  files: { name: string; data_url: string }[],
) {
  return post<{ error: string; data_files: DataFiles }>(
    `data-files/upload/${id}/${lib(library)}`,
    files,
  )
}

export function removeDataFiles(
  library: string,
  id: number,
  relpaths: string[],
) {
  return post<{ data_files: DataFiles; errors?: Record<string, string> }>(
    `data-files/remove/${id}/${lib(library)}`,
    relpaths,
  )
}

// }}}

// Notes {{{

/** The note on one author, tag, series and so on: HTML, '' for none. */
export function getNote(
  library: string,
  field: string,
  item: string,
): Promise<{ item_id: number; html: string }> {
  return request(
    `get-note-from-item-val/${encodeURIComponent(field)}/${encodeURIComponent(item)}/${lib(library)}`,
  )
}

/**
 * Save a note. Pictures are sent as calibre's editor sends them: each `src`
 * in the HTML is a key in `images`, either a new picture as a data: URL or
 * one the note already had, by its get-note-resource URL.
 */
export function setNote(
  library: string,
  field: string,
  itemId: number,
  note: {
    html: string
    searchable_text: string
    images: Record<string, { data: string; filename?: string }>
  },
): Promise<string> {
  return post<string>(
    `set-note/${encodeURIComponent(field)}/${itemId}/${lib(library)}`,
    note,
    { as: 'text' },
  )
}

// }}}

/** A file as a data: URL, for the endpoints that take JSON. */
export function readAsDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result as string)
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

/** What to tell someone when the server said no. */
export function errorText(e: unknown): string {
  if (e instanceof ServerError) {
    if (e.status === 403) return 'The server did not allow this change.'
    if (e.status === 0) return 'The server could not be reached.'
    // calibre's errors are short text. A page of HTML is not worth showing.
    const text = e.message.trim()
    if (text && text.length < 200 && !text.startsWith('<')) return text
    return `The server answered with an error (${e.status}).`
  }
  if (e instanceof Error) return e.message
  return 'Something went wrong.'
}
