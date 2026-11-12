// The Add books dialog: a place to drop or choose book files, and each
// file's upload under it.
import { IconFileUpload } from '@tabler/icons-react'
import type { Upload } from '@/lib/model/files'
import { FormDialog } from '@/components/app/Dialogs'
import { FilePicker } from '@/components/app/FilePicker'
import { UploadRow } from './UploadRow'

export function AddBooksDialog({
  open,
  onOpenChange,
  uploads,
  onPick,
  onOpenBook,
  onAddAnyway,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  uploads: Upload[]
  onPick: (files: File[]) => void
  onOpenBook: (id: number) => void
  onAddAnyway: (upload: Upload) => void
}) {
  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Add books"
      description="calibre reads the title and authors from each file."
      className="flex max-h-[85dvh] flex-col"
    >
      <FilePicker label="Book files" multiple drop onPick={onPick}>
        {/* Marks this dialog, so a drop beside it is not taken for the editor's. */}
        <button
          type="button"
          data-add-books
          className="flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-sm text-muted-foreground transition-colors outline-none hover:bg-muted/50 focus-visible:ring-[3px] focus-visible:ring-ring/50 data-[over]:border-ring data-[over]:bg-muted/50"
        >
          <IconFileUpload className="size-6" />
          <span>
            Drop book files here, or{' '}
            <span className="text-foreground underline underline-offset-2">
              choose files
            </span>
          </span>
        </button>
      </FilePicker>
      {uploads.length > 0 && (
        <ul
          aria-label="Uploads"
          className="-mx-1 flex min-h-0 flex-col gap-1 overflow-y-auto px-1"
        >
          {uploads.map((u) => (
            <UploadRow
              key={u.key}
              job={u}
              onOpen={onOpenBook}
              onAddAnyway={() => onAddAnyway(u)}
            />
          ))}
        </ul>
      )}
    </FormDialog>
  )
}
