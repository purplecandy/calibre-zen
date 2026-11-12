// A change sent to the server: saving a note, deleting a book, turning on
// full-text search. Every one goes through useAction, which keeps the busy
// state, says what happened, and brings the cache up to date, so a component
// writes no try/catch/finally and no busy flag of its own.
//
//   const remove = useAction({
//     run: (id: number) => deleteBooks(library, [id]),
//     done: 'Book deleted',
//     after: () => afterWrite(library),
//   })
//   <Button disabled={remove.busy} onClick={() => remove.run(book.id)}>
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { describeError, type Wording } from './errors'

export interface ActionOptions<V, R> {
  /** The change itself. A local check can throw an Error with the sentence to show. */
  run: (vars: V) => Promise<R>
  /** What to say when it worked, as a toast. Left out, nothing is said. */
  done?: string | ((result: R, vars: V) => string | undefined)
  /** Bring the cache up to date: an invalidate helper from lib/queries. */
  after?: (result: R, vars: V) => unknown
  /**
   * Where a failure is said: a toast (the default), or `inline`, for a form
   * that shows it beside its fields, from `error`.
   */
  failure?: 'toast' | 'inline'
  /** This action's own words for some failures (lib/errors). */
  wording?: Wording
}

export interface Action<V, R> {
  /** Run it. Resolves to the result, or to undefined when it failed. Never throws. */
  run: (vars: V) => Promise<R | undefined>
  busy: boolean
  /** With `failure: 'inline'`, the sentence for the last failure; '' otherwise. */
  error: string
  /** Forget the last result and failure, as when a dialog opens again. */
  reset: () => void
}

export function useAction<V = void, R = unknown>(
  options: ActionOptions<V, R>,
): Action<V, R> {
  const { run, done, after, failure = 'toast', wording } = options
  const m = useMutation<R, unknown, V>({
    mutationFn: run,
    onSuccess: async (result, vars) => {
      await after?.(result, vars)
      const said = typeof done === 'function' ? done(result, vars) : done
      if (said) toast.success(said)
    },
    onError: (e) => {
      if (failure === 'toast') toast.error(describeError(e, wording).text)
    },
  })
  return {
    run: (vars) => m.mutateAsync(vars).catch(() => undefined),
    busy: m.isPending,
    error:
      failure === 'inline' && m.error
        ? describeError(m.error, wording).text
        : '',
    reset: m.reset,
  }
}
