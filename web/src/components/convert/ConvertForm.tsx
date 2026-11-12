// The conversion itself: the book, From and To, the button that starts it
// and where it has got to, and calibre's options under them.
import { useMemo, useState } from 'react'
import { IconAlertTriangle, IconTransform } from '@tabler/icons-react'
import { useAction } from '@/lib/action'
import {
  CONVERSION_ERRORS,
  jobStatus,
  startConversion,
  type ConversionData,
} from '@/lib/conversion'
import { describeError } from '@/lib/errors'
import { useEventListener, useOnline } from '@/lib/hooks'
import {
  defaultsOf,
  groupsFor,
  jobState,
  optionValues,
  type Group,
  type Job,
} from '@/lib/model/conversion'
import { useConversionJob } from '@/lib/queries'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { BookHeader } from './BookHeader'
import { FormatChoice } from './FormatChoice'
import { JobStatus } from './JobStatus'
import { OptionGroups } from './OptionGroups'

export function ConvertForm({
  data,
  loading,
  input,
  output,
  setInput,
  setOutput,
  back,
}: {
  data: ConversionData
  loading: boolean
  input: string
  output: string
  setInput: (f: string) => void
  setOutput: (f: string) => void
  back: string
}) {
  const { library } = useLibraryContext()
  const online = useOnline()
  const opts = data.conversion_options
  // What has been changed here. It outlives a change of format, for the
  // options both formats share.
  const [changes, setChanges] = useState<Record<string, unknown>>({})
  const values = useMemo(() => optionValues(opts, changes), [opts, changes])
  const groups = groupsFor(opts, input, output)

  // Starting a job, then following it until it ends (lib/queries): the
  // server adds the new file to the book when it is asked after the job is
  // done, and a dropped status request is asked again before the page
  // gives up.
  const [jobId, setJobId] = useState<number | null>(null)
  const start = useAction({
    run: () => startConversion(library, data.book_id, input, output, values),
    failure: 'inline',
    wording: CONVERSION_ERRORS,
  })
  const followed = useConversionJob(library, jobId)
  const job: Job = start.busy
    ? { state: 'running', percent: 0, msg: '' }
    : start.error
      ? { state: 'error', message: start.error }
      : jobId === null
        ? { state: 'idle' }
        : followed.error
          ? {
              state: 'error',
              message: describeError(followed.error, CONVERSION_ERRORS).text,
            }
          : jobState(followed.status)

  // Leaving now would leave the new file unadded.
  useEventListener(
    job.state === 'running' ? window : null,
    'beforeunload',
    (e) => e.preventDefault(),
  )

  const convert = async () => {
    setJobId(null)
    const id = await start.run()
    if (id !== undefined) setJobId(id)
  }

  const cancel = () => {
    if (jobId !== null) void jobStatus(library, jobId, true).catch(() => {})
  }

  const restore = (group: Group) =>
    setChanges((c) => ({ ...c, ...defaultsOf(group, opts) }))

  const running = job.state === 'running'

  return (
    <>
      <BookHeader id={data.book_id} title={data.title} authors={data.authors} />

      {data.input_formats.length === 0 ? (
        <Alert>
          <IconAlertTriangle />
          <AlertTitle>Nothing to convert</AlertTitle>
          <AlertDescription>
            This book has no file in a format calibre can convert from.
          </AlertDescription>
        </Alert>
      ) : (
        <>
          <section className="grid gap-4 rounded-xl border p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <FormatChoice
                label="From"
                value={input}
                formats={data.input_formats}
                disabled={running || loading}
                onChange={setInput}
              />
              <FormatChoice
                label="To"
                value={output}
                formats={data.output_formats}
                disabled={running || loading}
                onChange={setOutput}
              />
            </div>
            <JobStatus job={job} id={data.book_id} back={back} />
            <div className="flex flex-wrap items-center gap-3">
              {running ? (
                <Button variant="outline" onClick={cancel}>
                  Stop
                </Button>
              ) : (
                <Button
                  onClick={() => void convert()}
                  disabled={!online || loading || !input || !output}
                >
                  <IconTransform />
                  Convert to {output}
                </Button>
              )}
              {!online && (
                <span className="text-sm text-muted-foreground">
                  You can convert once you are back online.
                </span>
              )}
            </div>
          </section>

          <OptionGroups
            groups={groups}
            data={data}
            values={values}
            running={running}
            onChange={(name, v) => setChanges((c) => ({ ...c, [name]: v }))}
            onRestore={restore}
          />
        </>
      )}
    </>
  )
}
