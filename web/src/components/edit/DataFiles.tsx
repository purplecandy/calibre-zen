// A book's data files: anything kept beside its books in the library's
// data folder, such as a map, an audio file or notes in a PDF. Listed in the
// book's details, to download, and to add or remove where that is allowed.
import { useState } from 'react'
import { IconFile, IconLoader2, IconPlus, IconTrash } from '@tabler/icons-react'
import { useAction } from '@/lib/action'
import type { Book } from '@/lib/api'
import {
  dataFileUrl,
  removeDataFiles,
  uploadDataFiles,
  type DataFiles as Files,
} from '@/lib/edit'
import { formatSize } from '@/lib/format'
import { dataFileName, dataFilePath, readAsDataUrl } from '@/lib/model/files'
import { dataFilesChanged, useCanEdit } from '@/lib/queries'
import { ConfirmDialog } from '@/components/app/Dialogs'
import { FilePicker } from '@/components/app/FilePicker'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Button } from '@/components/ui/button'

export function DataFiles({ book }: { book: Book & { id: number } }) {
  const { library } = useLibraryContext()
  const access = useCanEdit(library)
  const [removing, setRemoving] = useState<string | null>(null)
  const [replacing, setReplacing] = useState<File[] | null>(null)
  const files = (book.data_files as Files | undefined) ?? {}
  const paths = Object.keys(files).sort((a, b) => a.localeCompare(b))

  // The book's cached details take the new list, so nothing is fetched
  // again. calibre can keep some files and refuse others: the list is
  // taken either way, and the refusal is what is said.
  const upload = useAction({
    run: async (chosen: File[]) => {
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
      dataFilesChanged(library, book.id, r.data_files)
      if (r.error) throw new Error(r.error)
      return true
    },
    done: (_, chosen) =>
      chosen.length === 1
        ? `Added ${chosen[0].name}`
        : `Added ${chosen.length} files`,
  })
  const remove = useAction({
    run: async (relpath: string) => {
      const r = await removeDataFiles(library, book.id, [relpath])
      dataFilesChanged(library, book.id, r.data_files)
      const err = r.errors?.[relpath]
      if (err) throw new Error(err)
      return true
    },
    done: (_, relpath) => `Deleted ${dataFileName(relpath)}`,
  })
  const busy = upload.busy || remove.busy

  if (!paths.length && !access.allowed) return null

  const choose = (chosen: File[]) => {
    if (chosen.some((f) => dataFilePath(f.name) in files)) setReplacing(chosen)
    else void upload.run(chosen)
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
                title={`Download ${dataFileName(p)}`}
              >
                {dataFileName(p)}
              </a>
              <span className="text-xs text-muted-foreground">
                {formatSize(files[p].size)}
              </span>
              {access.allowed && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  aria-label={`Delete ${dataFileName(p)}`}
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
        <FilePicker label="Data files to add" multiple onPick={choose}>
          <Button variant="outline" size="sm" disabled={busy}>
            <IconPlus />
            Add data files
          </Button>
        </FilePicker>
      )}

      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(o) => !o && setRemoving(null)}
        title={`Delete ${removing ? dataFileName(removing) : ''}?`}
        description="The file is deleted for good. It does not go to the trash."
        confirm="Delete"
        destructive
        onConfirm={async () => {
          if (removing && (await remove.run(removing))) setRemoving(null)
        }}
      />

      <ConfirmDialog
        open={replacing !== null}
        onOpenChange={(o) => !o && setReplacing(null)}
        title="Replace files with the same name?"
        description={`${(replacing ?? [])
          .filter((f) => dataFilePath(f.name) in files)
          .map((f) => f.name)
          .join(', ')} will be replaced by the new ${
          (replacing ?? []).length === 1 ? 'one' : 'ones'
        }.`}
        confirm="Replace"
        onConfirm={async () => {
          if (replacing && (await upload.run(replacing))) setReplacing(null)
        }}
      />
    </section>
  )
}
