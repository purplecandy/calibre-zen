// What can be done to a book from its details: edit it, add notes, copy or
// move it to another library, delete it. When this browser may not change
// the library, the buttons are not there and one line says why.
import { useState } from 'react'
import {
  IconCopy,
  IconDots,
  IconLock,
  IconNotes,
  IconPencil,
  IconTrash,
} from '@tabler/icons-react'
import { toast } from 'sonner'
import type { Book, LibraryInfo } from '@/lib/api'
import { deleteBooks, errorText } from '@/lib/edit'
import { afterWrite, useCanEdit } from '@/lib/edit-queries'
import { useServerInfo } from '@/lib/queries'
import { setView } from '@/lib/state'
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { CopyToLibrary } from './CopyToLibrary'
import { startEditing } from './EditBook'
import { NotePicker } from './Notes'

export function BookActions({
  library,
  info,
  book,
}: {
  library: string
  info: LibraryInfo | undefined
  book: Book & { id: number }
}) {
  const access = useCanEdit(library)
  const server = useServerInfo()
  const [dialog, setDialog] = useState<'delete' | 'copy' | 'notes' | null>(null)

  if (!access.allowed) {
    if (!access.reason) return null
    return (
      <p className="flex gap-2 text-xs text-muted-foreground">
        <IconLock className="mt-px size-3.5 shrink-0" />
        {access.reason}
      </p>
    )
  }

  const others = Object.keys(server.data?.library_map ?? {}).filter(
    (l) => l !== library,
  )
  const notes = (info?.fields_that_support_notes ?? []).length > 0

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={startEditing}>
        <IconPencil />
        Edit
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className="size-8"
            aria-label="More"
          >
            <IconDots />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          {notes && (
            <DropdownMenuItem onSelect={() => setDialog('notes')}>
              <IconNotes className="size-4 text-muted-foreground" />
              Notes
            </DropdownMenuItem>
          )}
          {others.length > 0 && (
            <DropdownMenuItem onSelect={() => setDialog('copy')}>
              <IconCopy className="size-4 text-muted-foreground" />
              Copy to another library
            </DropdownMenuItem>
          )}
          {(notes || others.length > 0) && <DropdownMenuSeparator />}
          <DropdownMenuItem
            variant="destructive"
            onSelect={() => setDialog('delete')}
          >
            <IconTrash className="size-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <DeleteBook
        library={library}
        book={book}
        open={dialog === 'delete'}
        onOpenChange={(o) => setDialog(o ? 'delete' : null)}
      />
      {others.length > 0 && (
        <CopyToLibrary
          library={library}
          libraries={others.map((id) => [id, server.data!.library_map[id]])}
          book={book}
          open={dialog === 'copy'}
          onOpenChange={(o) => setDialog(o ? 'copy' : null)}
        />
      )}
      {notes && info && (
        <NotePicker
          library={library}
          info={info}
          book={book}
          open={dialog === 'notes'}
          onOpenChange={(o) => setDialog(o ? 'notes' : null)}
        />
      )}
    </div>
  )
}

function DeleteBook({
  library,
  book,
  open,
  onOpenChange,
}: {
  library: string
  book: Book & { id: number }
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const [busy, setBusy] = useState(false)
  const remove = async () => {
    setBusy(true)
    try {
      await deleteBooks(library, [book.id])
      onOpenChange(false)
      setView({ book: null }, { replace: true })
      afterWrite(library)
      toast.success(`Deleted “${book.title}”`)
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete “{book.title}”?</AlertDialogTitle>
          <AlertDialogDescription>
            The book and its files go to the library’s trash. You can bring them
            back from calibre’s Trash on the desktop for a while.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={busy}
            onClick={(e) => {
              e.preventDefault()
              void remove()
            }}
            variant="destructive"
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
