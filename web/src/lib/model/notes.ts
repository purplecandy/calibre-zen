// Notes on the authors, series, tags and so on of a book. calibre keeps one
// note per item, shared by every book that has it.
import { sortBy } from 'remeda'
import type { Book, LibraryInfo } from '@/lib/api'
import { NOTE_ORDER, rank } from './fields'

export interface NoteItem {
  field: string
  value: string
  label: string
}

type WithNotes = Record<string, Record<string, number>>

/** The items of `book` that can carry a note, field by field. */
export function noteItems(info: LibraryInfo, book: Book): NoteItem[] {
  const out: NoteItem[] = []
  const fields = sortBy(info.fields_that_support_notes, (f) =>
    rank(NOTE_ORDER, f),
  )
  for (const field of fields) {
    const v = book[field]
    const values = Array.isArray(v) ? (v as string[]) : v ? [String(v)] : []
    for (const value of values) {
      out.push({
        field,
        value,
        label:
          field === 'languages' ? (book.lang_names?.[value] ?? value) : value,
      })
    }
  }
  return out
}

/** Whether the item has a note, as the book's details say. */
export function hasNote(book: Book, item: NoteItem): boolean {
  const notes = book.items_with_notes as WithNotes | undefined
  return !!notes?.[item.field]?.[item.value]
}

const EXT: Record<string, string> = {
  'image/jpeg': 'jpg',
  'image/png': 'png',
  'image/gif': 'gif',
  'image/webp': 'webp',
  'image/svg+xml': 'svg',
}

/**
 * The HTML and pictures set-note wants. A new picture is a data: URL in the
 * editor; it is sent once, under a key that stands in its place. One the
 * note had already is named by its address, so calibre keeps it.
 */
export function notePayload(html: string, text: string) {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  const images: Record<string, { data: string; filename?: string }> = {}
  let n = 0
  doc.querySelectorAll('img[src]').forEach((img) => {
    const src = img.getAttribute('src')!
    if (src.startsWith('data:')) {
      // calibre swaps keys in with one regex alternation, so no key may
      // begin another: -1- is not the start of -10-.
      const key = `zen-note-picture-${++n}-`
      const mime = src.slice(5, src.indexOf(';'))
      images[key] = {
        data: src,
        filename: `picture-${n}.${EXT[mime] ?? 'png'}`,
      }
      img.setAttribute('src', key)
    } else if (src.includes('get-note-resource/')) {
      images[src] = { data: src }
    }
  })
  const empty = !text.trim() && !doc.querySelector('img')
  return {
    html: empty ? '' : doc.body.innerHTML,
    searchable_text: text,
    images,
  }
}
