// Where a conversion is: running, done with its new file to download,
// failed with what calibre said, or not started.
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconDownload,
} from '@tabler/icons-react'
import { downloadUrl } from '@/lib/api'
import { formatSize } from '@/lib/format'
import type { Job } from '@/lib/model/conversion'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'

export function JobStatus({
  job,
  id,
  back,
}: {
  job: Job
  id: number
  back: string
}) {
  const { library } = useLibraryContext()
  switch (job.state) {
    case 'idle':
      return null
    case 'running':
      return (
        <div className="grid gap-2" role="status">
          <Progress
            value={Math.round(job.percent * 100)}
            aria-label="Conversion progress"
          />
          <p className="text-sm text-muted-foreground">
            {job.msg || 'Converting…'} Keep this page open until it is done.
          </p>
        </div>
      )
    case 'done':
      return (
        <div className="grid gap-3" role="status">
          <p className="flex items-center gap-2 text-sm">
            <IconCircleCheck className="size-4 text-primary" />
            Converted. The {job.fmt} file is now part of the book.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm">
              <a href={downloadUrl(library, id, job.fmt)} download>
                <IconDownload />
                {job.fmt}
                <span className="font-normal opacity-70">
                  {formatSize(job.size)}
                </span>
              </a>
            </Button>
            <Button asChild size="sm" variant="outline">
              <a href={back}>Back to the book</a>
            </Button>
          </div>
        </div>
      )
    case 'failed':
      return (
        <Alert variant="destructive">
          <IconAlertTriangle />
          <AlertTitle>
            {job.aborted
              ? 'The conversion took too long and was stopped'
              : 'The conversion did not finish'}
          </AlertTitle>
          {job.log && (
            <AlertDescription>
              <details className="w-full">
                <summary className="cursor-pointer">What calibre said</summary>
                <pre className="mt-2 max-h-80 overflow-auto text-xs whitespace-pre-wrap">
                  {job.log}
                </pre>
              </details>
            </AlertDescription>
          )}
        </Alert>
      )
    case 'error':
      return (
        <Alert variant="destructive">
          <IconAlertTriangle />
          <AlertTitle>The conversion did not start</AlertTitle>
          <AlertDescription>{job.message}</AlertDescription>
        </Alert>
      )
  }
}
