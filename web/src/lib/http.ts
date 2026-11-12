// Talking to calibre's server: every request the app makes goes through here,
// except uploads, which use XHR for their progress (lib/edit.ts, addBook).
//
// A request that needs a login gets a 401 the first time, the browser asks
// for the username and password, and every request after it carries them --
// the same as calibre's web app.
import { pickBy } from 'remeda'
import { server } from './base'

/** The server answered, and not with a yes. `status` is 0 when it never did. */
export class ServerError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

export interface RequestOptions extends RequestInit {
  /** How to read the answer: as JSON (the default), as text, or not at all. */
  as?: 'json' | 'text' | 'none'
}

/** A request to calibre's server, from a path without a leading slash. */
export async function request<T = unknown>(
  path: string,
  { as = 'json', ...init }: RequestOptions = {},
): Promise<T> {
  const res = await fetch(server(path), {
    credentials: 'same-origin',
    ...init,
    headers: { Accept: 'application/json', ...init.headers },
  })
  if (!res.ok) throw new ServerError(res.status, await res.text())
  if (as === 'none') return undefined as T
  return (as === 'json' ? await res.json() : await res.text()) as T
}

/**
 * A POST. A file or form is sent as it is, and anything else as JSON: an
 * object, a list, and also a string or `true`, which calibre reads as JSON.
 */
export function post<T = unknown>(
  path: string,
  body?: unknown,
  options: RequestOptions = {},
): Promise<T> {
  const raw =
    body === undefined ||
    body instanceof Blob ||
    body instanceof FormData ||
    body instanceof URLSearchParams ||
    body instanceof ArrayBuffer
  return request<T>(path, {
    method: 'POST',
    ...options,
    headers: raw
      ? options.headers
      : { 'Content-Type': 'application/json', ...options.headers },
    body: raw ? (body as BodyInit | undefined) : JSON.stringify(body),
  })
}

type Param = string | number | readonly string[] | undefined

/**
 * A query string, with its `?`, or '' when there is nothing in it. Empty
 * values are left out, and a list repeats its key.
 */
export function qs(params: Record<string, Param>): string {
  const q = new URLSearchParams()
  const kept = pickBy(params, (v) => v !== undefined && v !== '')
  for (const [k, v] of Object.entries(kept)) {
    if (Array.isArray(v)) for (const x of v as string[]) q.append(k, x)
    else q.set(k, String(v))
  }
  const s = q.toString()
  return s ? '?' + s : ''
}
