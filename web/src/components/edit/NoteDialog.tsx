// One item's note, such as an author's: read it, and write it where the
// library allows. calibre keeps one note per item, shared by every book that
// has it.
import { lazy, Suspense, useState } from 'react'
import { IconLoader2, IconPencil } from '@tabler/icons-react'
import { useAction } from '@/lib/action'
import { setNote } from '@/lib/edit'
import { htmlText, safeHtml } from '@/lib/html'
import { notePayload, type NoteItem } from '@/lib/model/notes'
import { noteChanged, useCanEdit, useNote } from '@/lib/queries'
import { FormDialog } from '@/components/app/Dialogs'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Section } from '@/components/app/Section'
import { Button } from '@/components/ui/button'
import { DialogFooter } from '@/components/ui/dialog'

const RichText = lazy(() => import('./RichText'))

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
            dangerouslySetInnerHTML={{ __html: safeHtml(html) }}
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
              onClick={() => setEditing({ html, text: htmlText(html) })}
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
