// The address bar: this page's parameters, read and written back, and the
// links from one page of the app to another. Each page's own model of its
// address is built on these: the library's is lib/state.ts.
import { app } from './base'
import { qs } from './http'

/** This page's parameters. */
export function readAddress(): URLSearchParams {
  return new URLSearchParams(location.search)
}

/** The `name` parameter of this page's address, '' when it has none. */
export function param(name: string): string {
  return readAddress().get(name) ?? ''
}

/** Whether this page's address has a `name` parameter at all. */
export function hasParam(name: string): boolean {
  return readAddress().has(name)
}

/** This page with `params`, empty ones left out, in the order given. */
export function addressFor(params: Parameters<typeof qs>[0]): string {
  return location.pathname + qs(params)
}

/**
 * Put `params` in the address bar. `replace` for what should not become a
 * step of its own in the history.
 */
export function writeAddress(
  params: Parameters<typeof qs>[0],
  {
    replace = false,
    state = null,
  }: { replace?: boolean; state?: unknown } = {},
): void {
  const url = addressFor(params)
  if (replace) history.replaceState(state, '', url)
  else history.pushState(state, '', url)
}

// Links {{{

// Written as these links always have been: each value percent-encoded, so a
// space is %20.
function link(page: string, params: Record<string, string | number>): string {
  const q = Object.entries(params)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')
  return app(page + '?' + q)
}

/** The library page, on `library`. */
export function libraryLink(library: string): string {
  return link('', { library })
}

/** The library page with one book's details open. */
export function bookLink(library: string, id: number): string {
  return link('', { library, book: id })
}

export function convertLink(library: string, id: number): string {
  return link('convert/', { library, id })
}

/** Searching the text of the books in `library`. */
export function searchLink(library: string): string {
  return link('search/', { library })
}

export function settingsLink(): string {
  return app('settings/')
}

// }}}
