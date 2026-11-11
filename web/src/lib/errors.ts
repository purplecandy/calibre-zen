// What to tell someone when something fails, and what they can do about it.
// One vocabulary for the whole app: a screen passes its own wording for the
// answers that mean something particular there.
import { ServerError } from './http'

/**
 * What a person can do next: try again, go back to the plain view, reload
 * the page, or sign in.
 */
export type ErrorAction = 'retry' | 'reset' | 'reload' | 'login'

export interface Described {
  text: string
  action: ErrorAction
}

/** A screen's own words for some failures. Anything left out gets the default. */
export interface Wording {
  /** What to say for an answer with this status. */
  status?: Partial<Record<number, string>>
  /** What to say for any other answer from the server. */
  server?: (e: ServerError) => string
  /** What to say when the server did not answer: no network, a broken reply. */
  other?: string
}

export const UNREACHABLE = 'The server could not be reached.'

/** The server's own message, or that it answered with `status`. */
export function serverSaid(e: ServerError): string {
  return e.message || `The server answered ${e.status}.`
}

function defaultServerText(e: ServerError): string {
  if (e.status === 403) return 'The server did not allow this change.'
  if (e.status === 0) return UNREACHABLE
  // calibre's errors are short text. A page of HTML is not worth showing.
  const text = e.message.trim()
  if (text && text.length < 200 && !text.startsWith('<')) return text
  return `The server answered with an error (${e.status}).`
}

function text(e: unknown, w: Wording): string {
  if (e instanceof ServerError) {
    return w.status?.[e.status] ?? (w.server ?? defaultServerText)(e)
  }
  if (w.other !== undefined) return w.other
  if (e instanceof Error) return e.message
  return 'Something went wrong.'
}

function action(e: unknown): ErrorAction {
  if (!(e instanceof ServerError)) {
    // fetch fails with a TypeError when there is no answer at all.
    return e instanceof TypeError ? 'retry' : 'reload'
  }
  if (e.status === 401) return 'login'
  if (e.status === 0 || e.status >= 500 || e.status === 408) return 'retry'
  // What was asked for does not fit: a book that is gone, a search that
  // cannot be read, a feature that is off.
  if ([400, 404, 412, 422].includes(e.status)) return 'reset'
  return 'reload'
}

/** What to tell someone about `e`, in a sentence, and what they can do. */
export function describeError(e: unknown, wording: Wording = {}): Described {
  return { text: text(e, wording), action: action(e) }
}

/**
 * Whether a failed read is worth one more try. A 401 is the browser asking
 * for the login, and a 404 will not get better; anything else gets one more
 * try.
 */
export function shouldRetry(failures: number, e: unknown): boolean {
  return failures < 1 && !(e instanceof ServerError && e.status < 500)
}
