// Notes on the authors, series, tags and so on of a book: read them from the
// book's details, and write them where the library allows. calibre keeps one
// note per item, shared by every book that has it.
import { lazy, Suspense, useState } from 'react'
import { sortBy } from 'remeda'
import DOMPurify from 'dompurify'
import { IconLoader2, IconNote, IconPencil } from '@tabler/icons-react'
import { useAction } from '@/lib/action'
import type { Book, LibraryInfo } from '@/lib/api'
import { setNote } from '@/lib/edit'
import { noteChanged, useCanEdit, useNote } from '@/lib/queries'
import { FormDialog } from '@/components/app/Dialogs'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Section } from '@/components/app/Section'
import { Button } from '@/components/ui/button'
import { DialogFooter } from '@/components/ui/dialog'

const RichText = lazy(() => import('./RichText'))

export interface NoteItem {
  field: string
  value: string
  label: string
}

type WithNotes = Record<string, Record<string, number>>

const FIRST = ['authors', 'series', 'tags', 'publisher']

/** The items of `book` that can carry a note, field by field. */
function noteItems(info: LibraryInfo, book: Book): NoteItem[] {
  const out: NoteItem[] = []
  const rank = (f: string) => {
    const i = FIRST.indexOf(f)
    return i < 0 ? FIRST.length : i
  }
  const fields = sortBy(info.fields_that_support_notes, rank)
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

function hasNote(book: Book, item: NoteItem): boolean {
  const notes = book.items_with_notes as WithNotes | undefined
  return !!notes?.[item.field]?.[item.value]
}

function sanitize(html: string): string {
  const clean = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
  const doc = new DOMParser().parseFromString(clean, 'text/html')
  doc.querySelectorAll('a[href]').forEach((a) => {
    a.setAttribute('target', '_blank')
    a.setAttribute('rel', 'noopener noreferrer')
  })
  return doc.body.innerHTML
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

/** One item's note: shown, and edited where that is allowed. */
export function NoteDialog({
  bookId,
  item,
  fieldName,
  onOpenChange,
}: {
  bookId: number
  item: NoteItem | null
  fieldName: string
  onOpenChange: (o: boolean) => void
}) {
  return (
    <FormDialog
      open={!!item}
      onOpenChange={onOpenChange}
      title={item?.label}
      description={fieldName}
      size="xl"
      className="flex max-h-[90dvh] flex-col"
    >
      {item && (
        <Section
          key={`${item.field}:${item.value}`}
          size="inline"
          failed="This note could not be loaded."
        >
          <NoteBody bookId={bookId} item={item} />
        </Section>
      )}
    </FormDialog>
  )
}

function NoteBody({ bookId, item }: { bookId: number; item: NoteItem }) {
  const { library } = useLibraryContext()
  const access = useCanEdit(library)
  const note = useNote(library, item.field, item.value)
  const [editing, setEditing] = useState<{ html: string; text: string } | null>(
    null,
  )
  const save = useAction({
    run: (edited: { html: string; text: string }) =>
      setNote(
        library,
        item.field,
        note.item_id,
        notePayload(edited.html, edited.text),
      ),
    after: (html) => noteChanged(library, item.field, item.value, bookId, html),
    done: (html) => (html ? 'Note saved' : 'Note removed'),
  })

  const html = note.html
  return (
    <>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {editing ? (
          <Suspense fallback={<div className="h-48 rounded-md border" />}>
            <RichText
              initial={html}
              images
              label={`Note on ${item.label}`}
              onChange={(h, text) => setEditing({ html: h, text })}
            />
          </Suspense>
        ) : html ? (
          <div
            className="zen-prose text-sm leading-relaxed [&_img]:max-w-full"
            dangerouslySetInnerHTML={{ __html: sanitize(html) }}
          />
        ) : (
          <p className="text-sm text-muted-foreground">
            There is no note here yet.
          </p>
        )}
      </div>
      {access.allowed && (
        <DialogFooter>
          {editing ? (
            <>
              <Button
                variant="outline"
                disabled={save.busy}
                onClick={() => setEditing(null)}
              >
                Cancel
              </Button>
              <Button
                disabled={save.busy}
                onClick={async () => {
                  if ((await save.run(editing)) !== undefined) setEditing(null)
                }}
              >
                {save.busy && <IconLoader2 className="animate-spin" />}
                Save note
              </Button>
            </>
          ) : (
            <Button
              variant="outline"
              onClick={() =>
                setEditing({
                  html,
                  text:
                    new DOMParser().parseFromString(html, 'text/html').body
                      .textContent ?? '',
                })
              }
            >
              <IconPencil />
              {html ? 'Edit note' : 'Write a note'}
            </Button>
          )}
        </DialogFooter>
      )}
    </>
  )
}

/** In the book's details: the items that have a note, to open and read. */
export function BookNotes({ book }: { book: Book & { id: number } }) {
  const { info } = useLibraryContext()
  const [open, setOpen] = useState<NoteItem | null>(null)
  const items = noteItems(info, book).filter((i) => hasNote(book, i))
  if (!items.length) return null
  const fm = info.field_metadata
  return (
    <section>
      <h3 className="mb-2 text-xs font-medium text-muted-foreground">Notes</h3>
      <div className="flex flex-wrap gap-1.5">
        {items.map((i) => (
          <Button
            key={`${i.field}:${i.value}`}
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={() => setOpen(i)}
            title={fm[i.field]?.name}
          >
            <IconNote className="size-3.5" />
            {i.label}
          </Button>
        ))}
      </div>
      <NoteDialog
        bookId={book.id}
        item={open}
        fieldName={open ? (fm[open.field]?.name ?? open.field) : ''}
        onOpenChange={(o) => !o && setOpen(null)}
      />
    </section>
  )
}

/** Every item of the book that can carry a note, to write one. */
export function NotePicker({
  book,
  open,
  onOpenChange,
}: {
  book: Book & { id: number }
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const { info } = useLibraryContext()
  const [item, setItem] = useState<NoteItem | null>(null)
  const fm = info.field_metadata
  const items = noteItems(info, book)
  const fields = [...new Set(items.map((i) => i.field))]
  return (
    <>
      <FormDialog
        open={open}
        onOpenChange={onOpenChange}
        title="Notes"
        description="A note belongs to an author, series or tag, so every book with it shows the same note."
        className="flex max-h-[85dvh] flex-col"
      >
        <div className="-mx-2 min-h-0 flex-1 overflow-y-auto px-2">
          {fields.length === 0 && (
            <p className="text-sm text-muted-foreground">
              This book has no authors, series or tags to write about.
            </p>
          )}
          {fields.map((f) => (
            <section key={f} className="mb-4">
              <h3 className="mb-1.5 text-xs font-medium text-muted-foreground">
                {fm[f]?.name ?? f}
              </h3>
              <ul className="flex flex-col">
                {items
                  .filter((i) => i.field === f)
                  .map((i) => (
                    <li key={i.value}>
                      <button
                        type="button"
                        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent focus-visible:bg-accent focus-visible:outline-none"
                        onClick={() => setItem(i)}
                      >
                        <span className="min-w-0 flex-1 truncate">
                          {i.label}
                        </span>
                        {hasNote(book, i) && (
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <IconNote className="size-3.5" />
                            Has a note
                          </span>
                        )}
                      </button>
                    </li>
                  ))}
              </ul>
            </section>
          ))}
        </div>
      </FormDialog>
      <NoteDialog
        bookId={book.id}
        item={item}
        fieldName={item ? (fm[item.field]?.name ?? item.field) : ''}
        onOpenChange={(o) => !o && setItem(null)}
      />
    </>
  )
}
