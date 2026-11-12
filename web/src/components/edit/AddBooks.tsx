// Adding books: choose files or drop them anywhere on the library, and each
// is uploaded to calibre's add-book in turn, which reads its title and
// authors. A book calibre thinks is there already waits for a yes.
import { useCallback, useEffect, useRef, useState } from 'react'
import { IconPlus } from '@tabler/icons-react'
import { addBook } from '@/lib/edit'
import { describeError } from '@/lib/errors'
import { useEventListener } from '@/lib/hooks'
import { isBook, type Upload } from '@/lib/model/files'
import { booksChanged, useCanEdit } from '@/lib/queries'
import { setView } from '@/lib/state'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Button } from '@/components/ui/button'
import { AddBooksDialog } from './AddBooksDialog'

const hasFiles = (e: DragEvent) =>
  !!e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files')

/** A dialog other than Add books is open, such as the editor. */
const busyElsewhere = () =>
  Array.from(
    document.querySelectorAll('[role="dialog"], [role="alertdialog"]'),
  ).some((d) => !d.querySelector('[data-add-books]'))

export function AddBooks() {
  const { library } = useLibraryContext()
  const access = useCanEdit(library)
  const [open, setOpen] = useState(false)
  const [over, setOver] = useState(false)
  const uploads = useUploads(library)

  const add = (files: File[], duplicates = false) => {
    uploads.queue(files, duplicates)
    setOpen(true)
  }

  // Files dropped anywhere on the library. While another dialog is open, a
  // drop that missed its target is swallowed, so the browser does not open
  // the file in place of the app.
  const dropTarget = access.allowed ? window : null
  useEventListener(dropTarget, 'dragover', (e) => {
    if (!hasFiles(e) || e.defaultPrevented) return
    e.preventDefault()
    if (busyElsewhere()) {
      e.dataTransfer!.dropEffect = 'none'
      return
    }
    setOver(true)
  })
  useEventListener(dropTarget, 'dragleave', (e) => {
    if (!e.relatedTarget) setOver(false)
  })
  useEventListener(dropTarget, 'drop', (e) => {
    setOver(false)
    if (!hasFiles(e) || e.defaultPrevented) return
    e.preventDefault()
    if (busyElsewhere()) return
    const files = Array.from(e.dataTransfer!.files).filter(isBook)
    if (files.length) add(files)
  })

  if (!access.allowed) return null

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Add books"
        title="Add books"
        onClick={() => setOpen(true)}
      >
        <IconPlus className="size-5" />
      </Button>
      {over && !open && (
        <div className="pointer-events-none fixed inset-3 z-40 flex items-center justify-center rounded-xl border-2 border-dashed border-ring bg-background/80 text-sm font-medium">
          Drop to add these books
        </div>
      )}
      <AddBooksDialog
        open={open}
        onOpenChange={(o) => {
          setOpen(o)
          if (!o && !uploads.busy) uploads.clear()
        }}
        uploads={uploads.list}
        onPick={add}
        onOpenBook={(id) => {
          setOpen(false)
          setView({ book: id })
        }}
        onAddAnyway={(u) => {
          uploads.remove(u)
          add([u.file], true)
        }}
      />
    </>
  )
}

/** The files given to Add books, uploaded one at a time in the order given. */
function useUploads(library: string) {
  const [list, setList] = useState<Upload[]>([])
  const running = useRef(false)
  // Each upload's number, which calibre also takes as the job's.
  const counter = useRef(0)

  const patch = (key: number, p: Partial<Upload>) =>
    setList((us) => us.map((u) => (u.key === key ? { ...u, ...p } : u)))

  const queue = useCallback((files: File[], duplicates: boolean) => {
    setList((us) => [
      ...us,
      ...files.map((file) => ({
        key: ++counter.current,
        file,
        duplicates,
        state: 'waiting' as const,
        progress: 0,
      })),
    ])
  }, [])

  useEffect(() => {
    if (running.current) return
    const next = list.find((u) => u.state === 'waiting')
    if (!next) return
    running.current = true
    patch(next.key, { state: 'sending' })
    addBook(library, next.file, next.key, next.duplicates, (progress) =>
      patch(next.key, { progress }),
    )
      .promise.then((result) => {
        patch(next.key, {
          result,
          progress: 1,
          state: result.book_id ? 'added' : 'duplicate',
        })
        if (result.book_id) booksChanged(library)
      })
      .catch((e) =>
        patch(next.key, { state: 'failed', error: describeError(e).text }),
      )
      .finally(() => {
        running.current = false
        setList((us) => [...us]) // look for the next one
      })
  }, [list, library])

  return {
    list,
    queue,
    remove: (u: Upload) => setList((us) => us.filter((x) => x.key !== u.key)),
    clear: () => setList([]),
    busy: list.some((u) => u.state === 'waiting' || u.state === 'sending'),
  }
}
