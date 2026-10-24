// /app/convert/?library=books&id=12: convert a book to another format, with
// calibre's options, and add the new file to the book. calibre does the work
// on the server; this page starts it and follows it to the end.
import { useEffect, useMemo, useRef, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconDownload,
  IconTransform,
} from '@tabler/icons-react'
import { downloadUrl, type Book } from '@/lib/api'
import { app } from '@/lib/base'
import {
  conversionData,
  groupsFor,
  jobStatus,
  namesIn,
  problem,
  startConversion,
  type ConversionData,
  type Group,
} from '@/lib/conversion'
import { formatSize } from '@/lib/format'
import { saveNow, useOnline } from '@/lib/offline'
import { queryClient, useServerInfo } from '@/lib/queries'
import { AppProviders } from '@/components/app/AppProviders'
import { PageHeader, param } from '@/components/app/PageHeader'
import { Cover } from '@/components/library/Cover'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { OptionField } from './OptionField'

export default function ConvertApp() {
  return (
    <AppProviders>
      <Convert />
    </AppProviders>
  )
}

type Job =
  | { state: 'idle' }
  | { state: 'running'; percent: number; msg: string }
  | { state: 'done'; fmt: string; size: number }
  | { state: 'failed'; log: string; aborted: boolean }
  | { state: 'error'; message: string }

function Convert() {
  const server = useServerInfo()
  const id = Number(param('id'))
  const asked = param('library')
  const library = server.data
    ? asked in server.data.library_map
      ? asked
      : server.data.default_library_id
    : undefined
  const back = library
    ? app(`?library=${encodeURIComponent(library)}&book=${id}`)
    : app()

  // '' until chosen: the server picks the book's best input and the
  // library's preferred output.
  const [input, setInput] = useState('')
  const [output, setOutput] = useState('')
  const data = useQuery({
    queryKey: ['conversion', library, id, input, output],
    queryFn: () => conversionData(library!, id, input, output),
    enabled: !!library && id > 0,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  })

  useEffect(() => {
    document.title = data.data
      ? `Convert ${data.data.title} · Calibre Zen`
      : 'Convert · Calibre Zen'
  }, [data.data])

  return (
    <div className="min-h-dvh">
      <PageHeader back={back} backLabel="Back to the book" title="Convert" />
      <main className="mx-auto grid max-w-3xl gap-6 px-4 py-6 sm:px-6">
        {data.isError ? (
          <Alert variant="destructive">
            <IconAlertTriangle />
            <AlertTitle>This book cannot be converted here</AlertTitle>
            <AlertDescription>{problem(data.error)}</AlertDescription>
          </Alert>
        ) : !data.data || !library ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <Form
            key={`${library}:${id}`}
            library={library}
            data={data.data}
            loading={data.isFetching}
            input={input || data.data.input_formats[0] || ''}
            output={output || data.data.output_formats[0] || ''}
            setInput={setInput}
            setOutput={setOutput}
            back={back}
          />
        )}
      </main>
    </div>
  )
}

function Form({
  library,
  data,
  loading,
  input,
  output,
  setInput,
  setOutput,
  back,
}: {
  library: string
  data: ConversionData
  loading: boolean
  input: string
  output: string
  setInput: (f: string) => void
  setOutput: (f: string) => void
  back: string
}) {
  const online = useOnline()
  const opts = data.conversion_options
  // What has been changed here. It outlives a change of format, for the
  // options both formats share.
  const [changes, setChanges] = useState<Record<string, unknown>>({})
  const values = useMemo(() => {
    const v: Record<string, unknown> = { ...opts.options }
    for (const [k, x] of Object.entries(changes)) if (k in v) v[k] = x
    return v
  }, [opts.options, changes])
  const groups = groupsFor(opts, input, output)
  const [job, setJob] = useState<Job>({ state: 'idle' })
  const jobId = useRef<number | null>(null)
  const book: Book & { id: number } = { id: data.book_id, title: data.title }

  // Follow a running job until it ends. The server adds the new file to the
  // book when it is asked after the job is done, so the page asks until then.
  useEffect(() => {
    if (job.state !== 'running' || jobId.current === null) return
    let stop = false
    const t = setTimeout(async () => {
      try {
        const s = await jobStatus(library, jobId.current!)
        if (stop) return
        if (s.running) {
          setJob({ state: 'running', percent: s.percent, msg: s.msg })
        } else if (s.ok && s.fmt) {
          jobId.current = null
          setJob({ state: 'done', fmt: s.fmt.toUpperCase(), size: s.size ?? 0 })
          // The library page opens from the kept copy: it must not have the
          // book without its new file.
          queryClient.removeQueries({
            queryKey: ['book', library, data.book_id],
          })
          queryClient.removeQueries({ queryKey: ['books'] })
          void saveNow()
        } else {
          jobId.current = null
          setJob({
            state: 'failed',
            log: [s.traceback, s.log].filter(Boolean).join('\n\n'),
            aborted: s.was_aborted,
          })
        }
      } catch (e) {
        if (!stop) setJob({ state: 'error', message: problem(e) })
      }
    }, 1000)
    return () => {
      stop = true
      clearTimeout(t)
    }
  }, [job, library, data.book_id])

  // Leaving now would leave the new file unadded.
  useEffect(() => {
    if (job.state !== 'running') return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [job.state])

  const start = async () => {
    setJob({ state: 'running', percent: 0, msg: '' })
    try {
      jobId.current = await startConversion(
        library,
        data.book_id,
        input,
        output,
        values,
      )
      setJob({ state: 'running', percent: 0, msg: '' })
    } catch (e) {
      setJob({ state: 'error', message: problem(e) })
    }
  }

  const cancel = () => {
    if (jobId.current !== null)
      void jobStatus(library, jobId.current, true).catch(() => {})
  }

  const isDisabled = (group: Group, name: string): boolean => {
    if (opts.disabled.includes(name)) return true
    const dep = group.depends?.[name]
    return !!dep && !!values[dep.on] !== dep.when
  }

  const restore = (group: Group) =>
    setChanges((c) => {
      const next = { ...c }
      for (const n of namesIn(group))
        if (n in opts.defaults) next[n] = opts.defaults[n]
      return next
    })

  const running = job.state === 'running'

  return (
    <>
      <div className="flex gap-4">
        <div className="w-16 shrink-0 sm:w-20">
          <Cover library={library} book={book} width={80} eager />
        </div>
        <div className="min-w-0">
          <h2 className="font-serif text-xl leading-tight font-medium">
            {data.title}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {data.authors.join(', ')}
          </p>
        </div>
      </div>

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
            <Status job={job} library={library} id={data.book_id} back={back} />
            <div className="flex flex-wrap items-center gap-3">
              {running ? (
                <Button variant="outline" onClick={cancel}>
                  Stop
                </Button>
              ) : (
                <Button
                  onClick={() => void start()}
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

          <section className="grid gap-2">
            <h3 className="text-sm font-medium">Options</h3>
            <p className="text-sm text-muted-foreground">
              These start from the settings this book was last converted with,
              or from the library&rsquo;s defaults.
            </p>
            <Accordion type="multiple" className="rounded-xl border px-4">
              {groups.map((group) => (
                <AccordionItem key={group.id} value={group.id}>
                  <AccordionTrigger>{group.title}</AccordionTrigger>
                  <AccordionContent className="grid gap-2">
                    {group.fields.map((field, i) =>
                      field.kind === 'heading' ? (
                        <h4
                          key={i}
                          className="mt-3 text-xs font-medium text-muted-foreground first:mt-0"
                        >
                          {field.label}
                        </h4>
                      ) : field.name in values ? (
                        <OptionField
                          key={field.name}
                          field={field}
                          group={group}
                          data={data}
                          value={values[field.name]}
                          disabled={running || isDisabled(group, field.name)}
                          onChange={(v) =>
                            setChanges((c) => ({ ...c, [field.name]: v }))
                          }
                        />
                      ) : null,
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="mt-2 justify-self-start"
                      disabled={running}
                      onClick={() => restore(group)}
                    >
                      Restore defaults
                    </Button>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </section>
        </>
      )}
    </>
  )
}

function FormatChoice({
  label,
  value,
  formats,
  disabled,
  onChange,
}: {
  label: string
  value: string
  formats: string[]
  disabled: boolean
  onChange: (f: string) => void
}) {
  const id = `format-${label.toLowerCase()}`
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="max-h-80">
          {formats.map((f) => (
            <SelectItem key={f} value={f}>
              {f}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function Status({
  job,
  library,
  id,
  back,
}: {
  job: Job
  library: string
  id: number
  back: string
}) {
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
