// Editing one book: every field calibre lets a person change, its cover and
// its files, over the book's details. Opened with ?edit=1 beside ?book=, so
// Back closes it. Only what changed is sent, in one set-fields call, as
// calibre's own app sends it.
import { useEffect, useMemo, useRef, useState } from 'react'
import { IconLoader2 } from '@tabler/icons-react'
import { toast } from 'sonner'
import type { Book, LibraryInfo } from '@/lib/api'
import { coverDataUrl, errorText, readAsDataUrl, setFields } from '@/lib/edit'
import { afterWrite, useCanEdit } from '@/lib/edit-queries'
import { useBook } from '@/lib/queries'
import { setView, useView } from '@/lib/state'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { CoverField, type CoverChange } from './CoverField'
import { FieldEditor } from './fields'
import { extension, FormatsField, type FormatChanges } from './FormatsField'
import {
  editableFields,
  initialValue,
  same,
  toChanges,
  type FieldSpec,
  type FormValue,
} from './model'

// Whether ?edit=1 was pushed here, so leaving goes Back rather than adding
// a step. A link straight to the editor leaves in place.
let pushed = false

export function startEditing() {
  pushed = true
  setView({ edit: true })
}

function leave() {
  if (pushed) {
    pushed = false
    history.back()
  } else {
    setView({ edit: false }, { replace: true })
  }
}

export function EditBook({
  library,
  info,
}: {
  library: string
  info: LibraryInfo | undefined
}) {
  const view = useView()
  const open = view.edit && !!view.book
  const book = useBook(library, open ? view.book : null)
  const access = useCanEdit(library)
  const dirty = useRef(false)
  const [asking, setAsking] = useState(false)

  useEffect(() => {
    if (!open) {
      dirty.current = false
      pushed = false
    }
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
          {book.data && info && access.allowed ? (
            <EditForm
              key={`${library}:${view.book}`}
              library={library}
              info={info}
              book={{ ...book.data, id: view.book! }}
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
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-sm text-muted-foreground">
              <DialogTitle className="sr-only">Edit book</DialogTitle>
              <DialogDescription>
                {access.reason ||
                  (book.isError
                    ? 'This book could not be loaded.'
                    : 'Loading…')}
              </DialogDescription>
              {(book.isError || access.reason) && (
                <Button variant="outline" onClick={leave}>
                  Close
                </Button>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
      <AlertDialog open={asking} onOpenChange={setAsking}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Leave without saving?</AlertDialogTitle>
            <AlertDialogDescription>
              Your changes to this book will be lost.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                dirty.current = false
                leave()
              }}
            >
              Leave
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

function EditForm({
  library,
  info,
  book,
  onDirty,
  onClose,
  onSaved,
}: {
  library: string
  info: LibraryInfo
  book: Book & { id: number }
  onDirty: (dirty: boolean) => void
  onClose: () => void
  onSaved: () => void
}) {
  const specs = useMemo(() => editableFields(info), [info])
  // What the form started from. A later refetch of the book does not move
  // the ground under what someone is typing.
  const [initial] = useState(() => {
    const v: Record<string, FormValue> = {}
    for (const s of specs) v[s.field] = initialValue(s, book)
    return v
  })
  const [values, setValues] = useState(initial)
  const [cover, setCoverChange] = useState<CoverChange>(null)
  const [formats, setFormats] = useState<FormatChanges>({
    removed: [],
    added: [],
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const changed = specs.filter((s) => !same(values[s.field], initial[s.field]))
  const dirty =
    changed.length > 0 ||
    cover !== null ||
    formats.added.length > 0 ||
    formats.removed.length > 0
  useEffect(() => {
    onDirty(dirty)
  }, [dirty, onDirty])

  const save = async () => {
    if (!dirty || saving) return
    setSaving(true)
    setError('')
    try {
      const changes: Record<string, unknown> = {}
      for (const s of changed)
        Object.assign(changes, toChanges(s, values[s.field]))
      if (cover === 'remove') changes.cover = null
      else if (cover) changes.cover = await coverDataUrl(cover)
      if (formats.removed.length) changes.removed_formats = formats.removed
      if (formats.added.length) {
        changes.added_formats = await Promise.all(
          formats.added.map(async (f) => ({
            ext: extension(f),
            data_url: await readAsDataUrl(f),
          })),
        )
      }
      afterWrite(library, await setFields(library, book.id, changes))
      toast.success('Saved')
      onSaved()
    } catch (e) {
      setError(errorText(e))
      setSaving(false)
    }
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
          library={library}
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
            <CoverField
              library={library}
              book={book}
              value={cover}
              onChange={setCoverChange}
            />
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
