// In a book's details: the items of the book that have a note, to open
// and read.
import { useState } from 'react'
import { IconNote } from '@tabler/icons-react'
import type { Book } from '@/lib/api'
import { hasNote, noteItems, type NoteItem } from '@/lib/model/notes'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Button } from '@/components/ui/button'
import { NoteDialog } from './NoteDialog'

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
