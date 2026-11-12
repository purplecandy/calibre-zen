// Copy or move a book into another library on this server, with calibre's
// own copy-to-library: the same choices for a book that is there already.
import { useState } from 'react'
import { IconLoader2 } from '@tabler/icons-react'
import { toast } from 'sonner'
import { useAction } from '@/lib/action'
import type { Book } from '@/lib/api'
import { copyToLibrary, type DuplicateAction } from '@/lib/edit'
import { booksChanged } from '@/lib/queries'
import { setView } from '@/lib/state'
import { FormDialog } from '@/components/app/Dialogs'
import { Choices } from '@/components/app/Field'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Button } from '@/components/ui/button'

const DUPLICATES: [DuplicateAction, string][] = [
  ['add', 'Copy it anyway'],
  ['add_formats_to_existing', 'Add its files to the book that is there'],
  ['ignore', 'Leave it out'],
]

export function CopyToLibrary({
  libraries,
  book,
  open,
  onOpenChange,
}: {
  /** The other libraries it can go to: id and name. */
  libraries: [string, string][]
  book: Book & { id: number }
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const { library } = useLibraryContext()
  const [target, setTarget] = useState(libraries[0]?.[0] ?? '')
  const [duplicates, setDuplicates] = useState<DuplicateAction>('add')
  const name = Object.fromEntries(libraries)[target] ?? target

  const copy = useAction({
    run: async (move: boolean) => {
      const r = await copyToLibrary(library, target, book.id, {
        move,
        duplicates,
      })
      if (!r?.ok) throw new Error(`“${book.title}” could not be copied.`)
      return r.payload.action
    },
    after: (action, move) => {
      booksChanged(target)
      if (move && action !== 'duplicate') booksChanged(library)
    },
    done: (action, move) =>
      action === 'duplicate'
        ? undefined
        : action === 'automerge'
          ? `Added its files to the same book in ${name}`
          : move
            ? `Moved to ${name}`
            : `Copied to ${name}`,
  })
  // Which button was pressed, for its spinner.
  const [moving, setMoving] = useState(false)
  const busy = copy.busy ? (moving ? 'move' : 'copy') : null

  const run = async (move: boolean) => {
    setMoving(move)
    const action = await copy.run(move)
    if (action === undefined) return
    onOpenChange(false)
    if (action === 'duplicate') {
      toast.info(`“${book.title}” is already in ${name}, so it was left out.`)
    } else if (move) {
      setView({ book: null }, { replace: true })
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Copy to another library"
      description={book.title}
      footer={
        <>
          <Button
            variant="outline"
            disabled={!!busy}
            onClick={() => void run(true)}
          >
            {busy === 'move' && <IconLoader2 className="animate-spin" />}
            Move
          </Button>
          <Button disabled={!!busy} onClick={() => void run(false)}>
            {busy === 'copy' && <IconLoader2 className="animate-spin" />}
            Copy
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        <Choices
          legend="Library"
          name="copy-to"
          value={target}
          onChange={setTarget}
          options={libraries}
        />
        <Choices
          legend="If the book is already there"
          name="copy-dup"
          value={duplicates}
          onChange={setDuplicates}
          options={DUPLICATES}
        />
      </div>
    </FormDialog>
  )
}
