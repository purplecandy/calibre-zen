// From a book's menu: every item of the book that can carry a note, to
// write one.
import { useState } from 'react'
import { IconNote } from '@tabler/icons-react'
import type { Book } from '@/lib/api'
import { hasNote, noteItems, type NoteItem } from '@/lib/model/notes'
import { FormDialog } from '@/components/app/Dialogs'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { NoteDialog } from './NoteDialog'

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
