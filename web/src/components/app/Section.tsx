// A region of a page that shows the server's data: the book list, a book's
// details, a note, a list in the sidebar. Inside a Section, a component reads
// with a suspense hook from lib/queries and gets its data, never a loading
// or error state. The Section shows those, the same way everywhere:
//
//   <Section failed="This book could not be loaded.">
//     <BookDetails ... />
//   </Section>
//
// While loading it shows Pending, which also says when there is no network
// and nothing kept to show. A failure shows Problem, with the sentence from
// lib/errors and the one thing to do about it: try again, go back to a plain
// view (`reset`), or reload.
import { Suspense, type ReactNode } from 'react'
import { QueryErrorResetBoundary } from '@tanstack/react-query'
import { ErrorBoundary } from 'react-error-boundary'
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-react'
import { describeError, type Wording } from '@/lib/errors'
import { useOnline } from '@/lib/hooks'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

/** How much room a Section's states take: the whole page, a panel, or a line. */
export type SectionSize = 'page' | 'panel' | 'inline'

export interface ResetTo {
  /** The button's label, such as "Show all books". */
  label: string
  /** Go back to a view that fits, such as the library with no filters. */
  run: () => void
}

export function Section({
  children,
  size = 'panel',
  failed,
  wording,
  reset,
  resetKeys,
  loading,
  offline,
}: {
  children: ReactNode
  size?: SectionSize
  /** The sentence that leads a failure, such as "This book could not be loaded." */
  failed?: string
  /** This region's own words for some failures (lib/errors). */
  wording?: Wording
  /** Offered when what was asked for does not fit, such as a sort this library lacks. */
  reset?: ResetTo
  /** A change to any of these clears a failure, such as opening another book. */
  resetKeys?: unknown[]
  /** Instead of the default Pending, for a region with a shape of its own. */
  loading?: ReactNode
  /** What to say while offline with nothing kept, instead of the default. */
  offline?: string
}) {
  return (
    <QueryErrorResetBoundary>
      {({ reset: clearQueries }) => (
        <ErrorBoundary
          onReset={clearQueries}
          resetKeys={resetKeys}
          fallbackRender={({ error, resetErrorBoundary }) => (
            <Problem
              size={size}
              error={error}
              failed={failed}
              wording={wording}
              retry={resetErrorBoundary}
              reset={reset}
            />
          )}
        >
          <Suspense
            fallback={loading ?? <Pending size={size} offline={offline} />}
          >
            {children}
          </Suspense>
        </ErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  )
}

const BOX: Record<SectionSize, string> = {
  page: 'flex h-dvh flex-col items-center justify-center gap-3 p-8 text-center',
  panel:
    'flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center',
  inline: 'flex flex-wrap items-center gap-2 px-2 py-1.5',
}

const TEXT: Record<SectionSize, string> = {
  page: 'max-w-sm text-sm',
  panel: 'max-w-sm text-sm',
  inline: 'text-xs text-muted-foreground',
}

/**
 * Waiting for the server. With no network a request waits for one, so that
 * is said instead: nothing kept from an earlier visit can stand in.
 */
export function Pending({
  size = 'panel',
  offline = 'You are offline, and this has not been opened in this browser before.',
}: {
  size?: SectionSize
  offline?: string
}) {
  const online = useOnline()
  return (
    <div className={BOX[size]} role="status">
      <p className={cn(TEXT[size], 'text-muted-foreground')}>
        {online ? 'Loading…' : offline}
      </p>
    </div>
  )
}

/** Something failed: what, why in a sentence, and the one thing to do. */
export function Problem({
  size = 'panel',
  error,
  failed,
  wording,
  retry,
  reset,
}: {
  size?: SectionSize
  error: unknown
  failed?: string
  wording?: Wording
  retry: () => void
  reset?: ResetTo
}) {
  const { text, action } = describeError(error, wording)
  const button =
    action === 'reset' && reset
      ? {
          label: reset.label,
          run: () => {
            reset.run()
            retry()
          },
        }
      : action === 'reload' || action === 'login'
        ? { label: 'Reload', run: () => location.reload() }
        : { label: 'Try again', run: retry }
  const inline = size === 'inline'
  return (
    <div className={BOX[size]} role="alert">
      {!inline && (
        <IconAlertTriangle className="size-6 text-muted-foreground" />
      )}
      <p className={TEXT[size]}>{failed ? `${failed} ${text}` : text}</p>
      <Button
        variant={inline ? 'link' : 'outline'}
        size="sm"
        className={inline ? 'h-auto p-0 text-xs' : undefined}
        onClick={button.run}
      >
        {!inline && button.label === 'Try again' && <IconRefresh />}
        {button.label}
      </Button>
    </div>
  )
}

/** Nothing to show, and what would show everything. */
export function Empty({
  text,
  action,
}: {
  text: string
  action?: { label: string; run: () => void }
}) {
  return (
    <div className={BOX.panel}>
      <p className="text-sm text-muted-foreground">{text}</p>
      {action && (
        <Button variant="outline" size="sm" onClick={action.run}>
          {action.label}
        </Button>
      )}
    </div>
  )
}
