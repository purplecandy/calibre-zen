// The books a search found, one per book, a batch at a time. Each batch
// asks for its passages when it is shown, and shows its books until they
// are in.
import { useEffect, useState } from 'react'
import { books, formatCount } from '@/lib/format'
import { FTS_ERRORS, type FtsQuery } from '@/lib/fts'
import { batches, formatsByBook } from '@/lib/model/fts'
import { useFtsSearch, useFtsSnippets } from '@/lib/queries'
import { Section } from '@/components/app/Section'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Result } from './Result'

/** Results shown at a time; each batch fetches its passages when shown. */
const BATCH = 20

export function Results({ query }: { query: FtsQuery }) {
  const d = useFtsSearch(query)
  const [shown, setShown] = useState(BATCH)
  useEffect(() => setShown(BATCH), [query])

  // One result per book, with each format the words were found in.
  const byBook = formatsByBook(d.results)
  const ids = [...byBook.keys()]
  const { left, total } = d.indexing_status

  return (
    <div className="grid gap-4">
      {left > 0 && (
        <div className="grid gap-2 rounded-lg border p-4 text-sm">
          <p>
            calibre has read {formatCount(total - left)} of {formatCount(total)}{' '}
            files so far. Some matches may be missing until it is done.
          </p>
          <Progress
            value={total ? ((total - left) / total) * 100 : 0}
            aria-label="Books read so far"
          />
        </div>
      )}
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {ids.length === 0
          ? left > 0
            ? 'No books contain these words yet.'
            : 'No books contain these words.'
          : `Found in ${books(ids.length)}`}
      </p>
      <ol className="grid gap-3">
        {batches(ids, shown, BATCH).map((batch) => {
          const props = {
            query,
            ids: batch,
            formats: byBook,
            metadata: d.metadata,
          }
          // A batch's passages are asked for when it is shown; until they
          // are in, its books are there without them.
          return (
            <Section
              key={batch.join(',')}
              size="inline"
              wording={FTS_ERRORS}
              loading={<Batch {...props} />}
            >
              <WithPassages {...props} />
            </Section>
          )
        })}
      </ol>
      {ids.length > shown && (
        <Button
          variant="outline"
          className="justify-self-center"
          onClick={() => setShown((n) => n + BATCH)}
        >
          Show more
        </Button>
      )}
    </div>
  )
}

interface BatchProps {
  query: FtsQuery
  ids: number[]
  formats: Map<number, string[]>
  metadata: Record<string, { title: string; authors: string }>
}

function WithPassages(props: BatchProps) {
  const snippets = useFtsSnippets(props.query, props.ids)
  return <Batch {...props} snippets={snippets} />
}

function Batch({
  ids,
  formats,
  metadata,
  snippets,
}: BatchProps & { snippets?: Record<string, { text: string }[]> }) {
  return (
    <>
      {ids.map((id) => (
        <Result
          key={id}
          id={id}
          title={metadata[id]?.title ?? ''}
          authors={metadata[id]?.authors ?? ''}
          formats={formats.get(id) ?? []}
          passages={
            snippets ? (snippets[id]?.map((s) => s.text) ?? []) : undefined
          }
        />
      ))}
    </>
  )
}
