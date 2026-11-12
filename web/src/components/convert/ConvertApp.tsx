// /app/convert/?library=books&id=12: convert a book to another format, with
// calibre's options, and add the new file to the book. calibre does the work
// on the server; this page starts it and follows it to the end.
import { useDeferredValue, useMemo, useState } from 'react'
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconDownload,
  IconTransform,
} from '@tabler/icons-react'
import { useAction } from '@/lib/action'
import { downloadUrl, type Book } from '@/lib/api'
import {
  CONVERSION_ERRORS,
  jobStatus,
  startConversion,
  type ConversionData,
} from '@/lib/conversion'
import {
  defaultsOf,
  groupsFor,
  isOff,
  jobState,
  optionValues,
  type Group,
  type Job,
} from '@/lib/model/conversion'
import { describeError } from '@/lib/errors'
import { authors, formatSize } from '@/lib/format'
import {
  useCurrentLibrary,
  useDocumentTitle,
  useEventListener,
  useOnline,
} from '@/lib/hooks'
import { useBook, useConversionData, useConversionJob } from '@/lib/queries'
import { bookLink, param } from '@/lib/url'
import { AppProviders } from '@/components/app/AppProviders'
import { Field } from '@/components/app/Field'
import {
  LibraryProvider,
  useLibraryContext,
} from '@/components/app/LibraryContext'
import { PageHeader } from '@/components/app/PageHeader'
import { Pending, Section } from '@/components/app/Section'
import { Cover } from '@/components/library/Cover'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
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

function Convert() {
  const id = Number(param('id'))
  const library = useCurrentLibrary(param('library'))
  const back = bookLink(library, id)

  // '' until chosen: the server picks the book's best input and the
  // library's preferred output. The form follows a step behind, so it stays
  // while the options for a new choice load.
  const [choice, setChoice] = useState({ input: '', output: '' })
  const asked = useDeferredValue(choice)

  return (
    <div className="min-h-dvh">
      <PageHeader back={back} backLabel="Back to the book" title="Convert" />
      <main className="mx-auto grid max-w-3xl gap-6 px-4 py-6 sm:px-6">
        <Section
          failed="This book cannot be converted here."
          wording={CONVERSION_ERRORS}
          resetKeys={[asked.input, asked.output]}
          loading={<Waiting />}
        >
          <LibraryProvider library={library}>
            <Options
              id={id}
              choice={choice}
              asked={asked}
              setChoice={setChoice}
              back={back}
            />
          </LibraryProvider>
        </Section>
      </main>
    </div>
  )
}

/** Until the book's options are in, the tab says only Convert. */
function Waiting() {
  useDocumentTitle('Convert')
  return <Pending />
}

interface Choice {
  input: string
  output: string
}

function Options({
  id,
  choice,
  asked,
  setChoice,
  back,
}: {
  id: number
  choice: Choice
  asked: Choice
  setChoice: (c: Choice) => void
  back: string
}) {
  const { library } = useLibraryContext()
  const data = useConversionData(library, id, asked.input, asked.output)
  useDocumentTitle(`Convert ${data.title}`)
  return (
    <Form
      key={`${library}:${id}`}
      data={data}
      loading={choice !== asked}
      input={choice.input || data.input_formats[0] || ''}
      output={choice.output || data.output_formats[0] || ''}
      setInput={(input) => setChoice({ ...choice, input })}
      setOutput={(output) => setChoice({ ...choice, output })}
      back={back}
    />
  )
}

/** The book's cover, at the version its metadata names. */
function BookCover({ id, title }: { id: number; title: string }) {
  const { library } = useLibraryContext()
  // The book's metadata, for its cover's version, so the cover is kept for
  // offline under an address that changes with it.
  const meta = useBook(library, id)
  const book: Book & { id: number } = {
    id,
    title,
    last_modified: meta.last_modified,
  }
  return <Cover book={book} width={80} eager />
}

function Form({
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
      <div className="flex gap-4">
        <div className="w-16 shrink-0 sm:w-20">
          <Section
            size="inline"
            loading={
              <div
                className="rounded-md bg-muted"
                style={{ aspectRatio: '2 / 3' }}
              />
            }
          >
            <BookCover id={data.book_id} title={data.title} />
          </Section>
        </div>
        <div className="min-w-0">
          <h2 className="font-serif text-xl leading-tight font-medium">
            {data.title}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {authors(data.authors)}
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
            <Status job={job} id={data.book_id} back={back} />
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
                          disabled={
                            running || isOff(opts, group, values, field.name)
                          }
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
    <Field label={label} id={id}>
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
    </Field>
  )
}

function Status({ job, id, back }: { job: Job; id: number; back: string }) {
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
