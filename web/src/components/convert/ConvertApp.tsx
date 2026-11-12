// /app/convert/?library=books&id=12: convert a book to another format, with
// calibre's options, and add the new file to the book. calibre does the work
// on the server; this page starts it and follows it to the end.
import { useDeferredValue, useState } from 'react'
import { CONVERSION_ERRORS } from '@/lib/conversion'
import { useCurrentLibrary, useDocumentTitle } from '@/lib/hooks'
import { useConversionData } from '@/lib/queries'
import { bookLink, param } from '@/lib/url'
import { AppProviders } from '@/components/app/AppProviders'
import {
  LibraryProvider,
  useLibraryContext,
} from '@/components/app/LibraryContext'
import { PageHeader } from '@/components/app/PageHeader'
import { Pending, Section } from '@/components/app/Section'
import { ConvertForm } from './ConvertForm'

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
    <ConvertForm
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
