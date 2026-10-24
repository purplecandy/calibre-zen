// Copy or move a book into another library on this server, with calibre's
// own copy-to-library: the same choices for a book that is there already.
import { useState } from 'react'
import { IconLoader2 } from '@tabler/icons-react'
import { toast } from 'sonner'
import type { Book } from '@/lib/api'
import { copyToLibrary, errorText, type DuplicateAction } from '@/lib/edit'
import { afterWrite } from '@/lib/edit-queries'
import { setView } from '@/lib/state'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

const DUPLICATES: [DuplicateAction, string][] = [
  ['add', 'Copy it anyway'],
  ['add_formats_to_existing', 'Add its files to the book that is there'],
  ['ignore', 'Leave it out'],
]

export function CopyToLibrary({
  library,
  libraries,
  book,
  open,
  onOpenChange,
}: {
  library: string
  libraries: [string, string][]
  book: Book & { id: number }
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const [target, setTarget] = useState(libraries[0]?.[0] ?? '')
  const [duplicates, setDuplicates] = useState<DuplicateAction>('add')
  const [busy, setBusy] = useState<'copy' | 'move' | null>(null)
  const name = Object.fromEntries(libraries)[target] ?? target

  const run = async (move: boolean) => {
    setBusy(move ? 'move' : 'copy')
    try {
      const r = await copyToLibrary(library, target, book.id, {
        move,
        duplicates,
      })
      if (!r?.ok) throw new Error(`“${book.title}” could not be copied.`)
      const action = r.payload.action
      onOpenChange(false)
      if (action === 'duplicate') {
        toast.info(`“${book.title}” is already in ${name}, so it was left out.`)
      } else {
        toast.success(
          action === 'automerge'
            ? `Added its files to the same book in ${name}`
            : move
              ? `Moved to ${name}`
              : `Copied to ${name}`,
        )
      }
      afterWrite(target)
      if (move && action !== 'duplicate') {
        setView({ book: null }, { replace: true })
        afterWrite(library)
      }
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Copy to another library</DialogTitle>
          <DialogDescription>{book.title}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-5">
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">Library</legend>
            <RadioGroup value={target} onValueChange={setTarget}>
              {libraries.map(([id, label]) => (
                <div key={id} className="flex items-center gap-2">
                  <RadioGroupItem value={id} id={`copy-to-${id}`} />
                  <Label htmlFor={`copy-to-${id}`} className="font-normal">
                    {label}
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">
              If the book is already there
            </legend>
            <RadioGroup
              value={duplicates}
              onValueChange={(v) => setDuplicates(v as DuplicateAction)}
            >
              {DUPLICATES.map(([v, label]) => (
                <div key={v} className="flex items-center gap-2">
                  <RadioGroupItem value={v} id={`copy-dup-${v}`} />
                  <Label htmlFor={`copy-dup-${v}`} className="font-normal">
                    {label}
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </fieldset>
        </div>
        <DialogFooter>
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
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
