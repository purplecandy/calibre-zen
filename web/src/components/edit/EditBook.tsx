// Editing one book: every field calibre lets a person change, its cover and
// its files, over the book's details. Opened with ?edit=1 beside ?book=, so
// Back closes it. Only what changed is sent, in one set-fields call, as
// calibre's own app sends it.
import { useEffect, useMemo, useRef, useState } from 'react'
import { IconLoader2 } from '@tabler/icons-react'
import { useAction } from '@/lib/action'
import type { Book } from '@/lib/api'
import { setFields } from '@/lib/edit'
import {
  editableFields,
  hasEdits,
  initialValues,
  same,
  setFieldsChanges,
  type CoverChange,
  type FieldSpec,
  type FormatChanges,
} from '@/lib/model/edit'
import { booksChanged, useBook, useCanEdit } from '@/lib/queries'
import { closeStep, useView } from '@/lib/state'
import { ConfirmDialog } from '@/components/app/Dialogs'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Pending, Section } from '@/components/app/Section'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { CoverField } from './CoverField'
import { FieldEditor } from './fields'
import { FormatsField } from './FormatsField'

// Leaving goes Back when the editor was opened here (startEditing in
// lib/state.ts), and stays in place for a link straight to it.
function leave() {
  closeStep('edit', { edit: false })
}

export function EditBook() {
  const { library } = useLibraryContext()
  const view = useView()
  const open = view.edit && !!view.book
  const access = useCanEdit(library)
  const dirty = useRef(false)
  const [asking, setAsking] = useState(false)

  useEffect(() => {
    if (!open) dirty.current = false
  }, [open])

  const close = () => {
    if (dirty.current) setAsking(true)
    else leave()
  }

  return (
    <>
      <Dialog open={open} onOpenChange={(o) => !o && close()}>
        <DialogContent
          showCloseButton={false}
          className="flex h-dvh max-h-dvh w-full max-w-none flex-col gap-0 rounded-none p-0 sm:h-[90dvh] sm:max-w-3xl sm:rounded-lg"
          onInteractOutside={(e) => e.preventDefault()}
        >
          {access.reason ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-sm text-muted-foreground">
              <DialogTitle className="sr-only">Edit book</DialogTitle>
              <DialogDescription>{access.reason}</DialogDescription>
              <Button variant="outline" onClick={leave}>
                Close
              </Button>
            </div>
          ) : open ? (
            <Section
              failed="This book could not be loaded."
              reset={{ label: 'Close', run: leave }}
              resetKeys={[library, view.book]}
              loading={<Waiting />}
            >
              {access.allowed ? (
                <EditLoaded
                  key={`${library}:${view.book}`}
                  id={view.book!}
                  onDirty={(d) => {
                    dirty.current = d
                  }}
                  onClose={close}
                  onSaved={() => {
                    dirty.current = false
                    leave()
                  }}
                />
              ) : (
                <Waiting />
              )}
            </Section>
          ) : null}
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={asking}
        onOpenChange={setAsking}
        title="Leave without saving?"
        description="Your changes to this book will be lost."
        cancel="Keep editing"
        confirm="Leave"
        onConfirm={() => {
          dirty.current = false
          setAsking(false)
          leave()
        }}
      />
    </>
  )
}

/** Waiting for the book, or for whether this browser may change it. */
function Waiting() {
  return (
    <>
      <DialogTitle className="sr-only">Edit book</DialogTitle>
      <Pending />
    </>
  )
}

function EditLoaded({
  id,
  ...props
}: Omit<Parameters<typeof EditForm>[0], 'book'> & { id: number }) {
  const { library } = useLibraryContext()
  const book = useBook(library, id)
  return <EditForm {...props} book={book} />
}

function EditForm({
  book,
  onDirty,
  onClose,
  onSaved,
}: {
  book: Book & { id: number }
  onDirty: (dirty: boolean) => void
  onClose: () => void
  onSaved: () => void
}) {
  const { library, info } = useLibraryContext()
  const specs = useMemo(() => editableFields(info), [info])
  // What the form started from. A later refetch of the book does not move
  // the ground under what someone is typing.
  const [initial] = useState(() => initialValues(specs, book))
  const [values, setValues] = useState(initial)
  const [cover, setCoverChange] = useState<CoverChange>(null)
  const [formats, setFormats] = useState<FormatChanges>({
    removed: [],
    added: [],
  })

  const edits = {
    fields: specs.filter((s) => !same(values[s.field], initial[s.field])),
    values,
    cover,
    formats,
  }
  const dirty = hasEdits(edits)
  useEffect(() => {
    onDirty(dirty)
  }, [dirty, onDirty])

  const send = useAction({
    run: async () => setFields(library, book.id, await setFieldsChanges(edits)),
    after: (books) => booksChanged(library, books),
    done: 'Saved',
    failure: 'inline',
  })
  const saving = send.busy
  const error = send.error

  const save = async () => {
    if (!dirty || saving) return
    if (await send.run()) onSaved()
  }

  const row = (s: FieldSpec) => {
    const id = `edit-${s.field.replace('#', '_c_')}`
    return (
      <div
        key={s.field}
        className={
          s.wide
            ? 'flex flex-col gap-1.5'
            : 'grid gap-1.5 sm:grid-cols-[8rem_minmax(0,1fr)] sm:items-start sm:gap-3'
        }
      >
        <Label
          htmlFor={id}
          className={`font-normal text-muted-foreground sm:truncate ${s.wide ? '' : 'sm:pt-2.5'}`}
        >
          {s.name}
        </Label>
        <FieldEditor
          spec={s}
          id={id}
          value={values[s.field]}
          initial={initial[s.field]}
          onChange={(v) => setValues((old) => ({ ...old, [s.field]: v }))}
        />
      </div>
    )
  }

  return (
    <div
      className="flex min-h-0 flex-1 flex-col"
      onKeyDown={(e) => {
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
          e.preventDefault()
          void save()
        }
      }}
    >
      <header className="flex items-center gap-3 border-b px-4 py-3 sm:px-6">
        <div className="min-w-0">
          <DialogTitle className="text-base">Edit book</DialogTitle>
          <DialogDescription className="truncate">
            {book.title}
          </DialogDescription>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        {/* On a phone: cover, fields, formats. Wider: cover and formats beside the fields. */}
        <div className="grid gap-6 sm:grid-cols-[10rem_minmax(0,1fr)] sm:grid-rows-[auto_1fr]">
          <div className="w-32 sm:col-start-1 sm:row-start-1 sm:w-full">
            <CoverField book={book} value={cover} onChange={setCoverChange} />
          </div>
          <div className="flex min-w-0 flex-col gap-4 sm:col-start-2 sm:row-span-2 sm:row-start-1">
            {specs.map(row)}
          </div>
          <section
            aria-labelledby="edit-formats"
            className="sm:col-start-1 sm:row-start-2"
          >
            <h3
              id="edit-formats"
              className="mb-1.5 text-sm text-muted-foreground"
            >
              Formats
            </h3>
            <FormatsField
              formats={book.formats ?? []}
              sizes={book.format_sizes ?? {}}
              value={formats}
              onChange={setFormats}
            />
          </section>
        </div>
      </div>

      <footer className="flex flex-col gap-2 border-t px-4 py-3 sm:flex-row sm:items-center sm:px-6">
        <p
          role="alert"
          className="min-w-0 flex-1 text-sm text-destructive empty:hidden"
        >
          {error}
        </p>
        <div className="flex justify-end gap-2 sm:ml-auto">
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void save()} disabled={!dirty || saving}>
            {saving && <IconLoader2 className="animate-spin" />}
            Save
          </Button>
        </div>
      </footer>
    </div>
  )
}
