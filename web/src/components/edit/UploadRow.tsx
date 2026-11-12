// One file in Add books: waiting, sending with its progress, added with a
// way to open it, already there with Add anyway, or failed with why.
import { IconAlertTriangle, IconCheck, IconCopy } from '@tabler/icons-react'
import { authors, formatSize } from '@/lib/format'
import type { Upload } from '@/lib/model/files'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'

export function UploadRow({
  job,
  onOpen,
  onAddAnyway,
}: {
  job: Upload
  onOpen: (id: number) => void
  onAddAnyway: () => void
}) {
  const r = job.result
  return (
    <li className="flex flex-col gap-1.5 rounded-md border px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        {job.state === 'added' ? (
          <IconCheck className="size-4 shrink-0 text-success" />
        ) : job.state === 'duplicate' ? (
          <IconCopy className="size-4 shrink-0 text-muted-foreground" />
        ) : job.state === 'failed' ? (
          <IconAlertTriangle className="size-4 shrink-0 text-destructive" />
        ) : null}
        <span className="min-w-0 flex-1 truncate font-medium">
          {r?.title || job.file.name}
        </span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {job.state === 'waiting'
            ? 'Waiting'
            : job.state === 'sending'
              ? job.progress < 1
                ? formatSize(job.file.size)
                : 'Reading'
              : null}
        </span>
        {job.state === 'added' && r?.book_id && (
          <Button
            variant="ghost"
            size="sm"
            className="h-7"
            onClick={() => onOpen(r.book_id!)}
          >
            Open
          </Button>
        )}
      </div>
      {job.state === 'sending' && (
        <Progress value={job.progress * 100} className="h-1" />
      )}
      {job.state === 'added' && r?.authors?.length ? (
        <p className="text-xs text-muted-foreground">by {authors(r.authors)}</p>
      ) : null}
      {job.state === 'duplicate' && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="flex-1">
            A book with this title and authors is already here.
          </span>
          <Button
            variant="outline"
            size="sm"
            className="h-7"
            onClick={onAddAnyway}
          >
            Add anyway
          </Button>
        </div>
      )}
      {job.state === 'failed' && (
        <p className="text-xs text-destructive">{job.error}</p>
      )}
    </li>
  )
}
