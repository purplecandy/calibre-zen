// Adding books: choose files or drop them anywhere on the library, and each
// is uploaded to calibre's add-book in turn, which reads its title and
// authors. A book calibre thinks is there already waits for a yes.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  IconAlertTriangle,
  IconCheck,
  IconCopy,
  IconFileUpload,
  IconPlus,
} from '@tabler/icons-react'
import { addBook, errorText, type AddResult } from '@/lib/edit'
import { afterWrite, useCanEdit } from '@/lib/edit-queries'
import { formatSize } from '@/lib/format'
import { setView } from '@/lib/state'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'

interface Job {
  key: number
  file: File
  duplicates: boolean
  state: 'waiting' | 'sending' | 'added' | 'duplicate' | 'failed'
  progress: number
  result?: AddResult
  error?: string
}

let counter = 0

export function AddBooks({ library }: { library: string }) {
  const access = useCanEdit(library)
  const [open, setOpen] = useState(false)
  const [jobs, setJobs] = useState<Job[]>([])
  const [over, setOver] = useState(false)
  const picker = useRef<HTMLInputElement>(null)
  const running = useRef(false)

  const patch = (key: number, p: Partial<Job>) =>
    setJobs((js) => js.map((j) => (j.key === key ? { ...j, ...p } : j)))

  const queue = useCallback((files: File[], duplicates = false) => {
    setJobs((js) => [
      ...js,
      ...files.map((file) => ({
        key: ++counter,
        file,
        duplicates,
        state: 'waiting' as const,
        progress: 0,
      })),
    ])
    setOpen(true)
  }, [])

  // One upload at a time, in the order they were given.
  useEffect(() => {
    if (running.current) return
    const next = jobs.find((j) => j.state === 'waiting')
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
        if (result.book_id) afterWrite(library)
      })
      .catch((e) => patch(next.key, { state: 'failed', error: errorText(e) }))
      .finally(() => {
        running.current = false
        setJobs((js) => [...js]) // look for the next one
      })
  }, [jobs, library])

  // Files dropped anywhere on the library.
  useEffect(() => {
    if (!access.allowed) return
    const hasFiles = (e: DragEvent) =>
      !!e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files')
    const onOver = (e: DragEvent) => {
      if (!hasFiles(e) || e.defaultPrevented) return
      e.preventDefault()
      setOver(true)
    }
    const onLeave = (e: DragEvent) => {
      if (!e.relatedTarget) setOver(false)
    }
    const onDrop = (e: DragEvent) => {
      setOver(false)
      if (!hasFiles(e) || e.defaultPrevented) return
      e.preventDefault()
      const files = Array.from(e.dataTransfer!.files)
      if (files.length) queue(files)
    }
    window.addEventListener('dragover', onOver)
    window.addEventListener('dragleave', onLeave)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragover', onOver)
      window.removeEventListener('dragleave', onLeave)
      window.removeEventListener('drop', onDrop)
    }
  }, [access.allowed, queue])

  if (!access.allowed) return null

  const busy = jobs.some((j) => j.state === 'waiting' || j.state === 'sending')

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
      <Dialog
        open={open}
        onOpenChange={(o) => {
          setOpen(o)
          if (!o && !busy) setJobs([])
        }}
      >
        <DialogContent className="flex max-h-[85dvh] flex-col sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Add books</DialogTitle>
            <DialogDescription>
              calibre reads the title and authors from each file.
            </DialogDescription>
          </DialogHeader>
          <button
            type="button"
            onClick={() => picker.current?.click()}
            onDragOver={(e) => {
              e.preventDefault()
              setOver(true)
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setOver(false)
              queue(Array.from(e.dataTransfer.files))
            }}
            className={cn(
              'flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-sm text-muted-foreground transition-colors outline-none hover:bg-muted/50 focus-visible:ring-[3px] focus-visible:ring-ring/50',
              over && 'border-ring bg-muted/50',
            )}
          >
            <IconFileUpload className="size-6" />
            <span>
              Drop book files here, or{' '}
              <span className="text-foreground underline underline-offset-2">
                choose files
              </span>
            </span>
          </button>
          <input
            ref={picker}
            type="file"
            multiple
            hidden
            aria-label="Book files"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? [])
              if (files.length) queue(files)
              e.target.value = ''
            }}
          />
          {jobs.length > 0 && (
            <ul
              aria-label="Uploads"
              className="-mx-1 flex min-h-0 flex-col gap-1 overflow-y-auto px-1"
            >
              {jobs.map((j) => (
                <JobRow
                  key={j.key}
                  job={j}
                  onOpen={(id) => {
                    setOpen(false)
                    setView({ book: id })
                  }}
                  onAddAnyway={() => {
                    setJobs((js) => js.filter((x) => x.key !== j.key))
                    queue([j.file], true)
                  }}
                />
              ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

function JobRow({
  job,
  onOpen,
  onAddAnyway,
}: {
  job: Job
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
        <p className="text-xs text-muted-foreground">
          by {r.authors.join(' & ')}
        </p>
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
