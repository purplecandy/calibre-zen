// A book's data files: anything kept beside its books in the library's
// data folder, such as a map, an audio file or notes in a PDF. Listed in the
// book's details, to download, and to add or remove where that is allowed.
import { useRef, useState } from 'react'
import { IconFile, IconLoader2, IconPlus, IconTrash } from '@tabler/icons-react'
import { toast } from 'sonner'
import type { Book } from '@/lib/api'
import {
  dataFileUrl,
  errorText,
  readAsDataUrl,
  removeDataFiles,
  uploadDataFiles,
  type DataFiles as Files,
} from '@/lib/edit'
import { useCanEdit } from '@/lib/edit-queries'
import { formatSize } from '@/lib/format'
import { queryClient } from '@/lib/queries'
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

const DIR = 'data/'

function nameOf(relpath: string) {
  return relpath.startsWith(DIR) ? relpath.slice(DIR.length) : relpath
}

export function DataFiles({
  library,
  book,
}: {
  library: string
  book: Book & { id: number }
}) {
  const access = useCanEdit(library)
  const picker = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [removing, setRemoving] = useState<string | null>(null)
  const [replacing, setReplacing] = useState<File[] | null>(null)
  const files = (book.data_files as Files | undefined) ?? {}
  const paths = Object.keys(files).sort((a, b) => a.localeCompare(b))

  if (!paths.length && !access.allowed) return null

  // The book's cached details take the new list, so nothing is fetched again.
  const update = (data_files: Files) => {
    queryClient.setQueryData(
      ['book', library, book.id],
      (old: Book | undefined) => old && { ...old, data_files },
    )
  }

  const upload = async (chosen: File[]) => {
    setBusy(true)
    try {
      const r = await uploadDataFiles(
        library,
        book.id,
        await Promise.all(
          chosen.map(async (f) => ({
            name: f.name,
            data_url: await readAsDataUrl(f),
          })),
        ),
      )
      update(r.data_files)
      if (r.error) toast.error(r.error)
      else
        toast.success(
          chosen.length === 1
            ? `Added ${chosen[0].name}`
            : `Added ${chosen.length} files`,
        )
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  const choose = (list: FileList | null) => {
    const chosen = Array.from(list ?? [])
    if (!chosen.length) return
    if (chosen.some((f) => DIR + f.name in files)) setReplacing(chosen)
    else void upload(chosen)
  }

  const remove = async (relpath: string) => {
    setBusy(true)
    try {
      const r = await removeDataFiles(library, book.id, [relpath])
      update(r.data_files)
      const err = r.errors?.[relpath]
      if (err) toast.error(err)
      else toast.success(`Deleted ${nameOf(relpath)}`)
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="data-files">
      <div className="mb-2 flex items-center gap-2">
        <h3
          id="data-files"
          className="text-xs font-medium text-muted-foreground"
        >
          Data files
        </h3>
        {busy && (
          <IconLoader2 className="size-3.5 animate-spin text-muted-foreground" />
        )}
      </div>
      {paths.length > 0 && (
        <ul className="mb-2 flex flex-col gap-0.5 text-sm">
          {paths.map((p) => (
            <li key={p} className="flex items-center gap-2">
              <IconFile className="size-4 shrink-0 text-muted-foreground" />
              <a
                href={dataFileUrl(library, book.id, p)}
                download
                className="min-w-0 flex-1 truncate hover:underline"
                title={`Download ${nameOf(p)}`}
              >
                {nameOf(p)}
              </a>
              <span className="text-xs text-muted-foreground">
                {formatSize(files[p].size)}
              </span>
              {access.allowed && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  aria-label={`Delete ${nameOf(p)}`}
                  disabled={busy}
                  onClick={() => setRemoving(p)}
                >
                  <IconTrash />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {access.allowed && (
        <>
          <Button
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => picker.current?.click()}
          >
            <IconPlus />
            Add data files
          </Button>
          <input
            ref={picker}
            type="file"
            multiple
            hidden
            aria-label="Data files to add"
            onChange={(e) => {
              choose(e.target.files)
              e.target.value = ''
            }}
          />
        </>
      )}

      <AlertDialog
        open={removing !== null}
        onOpenChange={(o) => !o && setRemoving(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {removing ? nameOf(removing) : ''}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              The file is deleted for good. It does not go to the trash.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => removing && void remove(removing)}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={replacing !== null}
        onOpenChange={(o) => !o && setReplacing(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Replace files with the same name?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {(replacing ?? [])
                .filter((f) => DIR + f.name in files)
                .map((f) => f.name)
                .join(', ')}{' '}
              will be replaced by the new{' '}
              {(replacing ?? []).length === 1 ? 'one' : 'ones'}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => replacing && void upload(replacing)}
            >
              Replace
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
