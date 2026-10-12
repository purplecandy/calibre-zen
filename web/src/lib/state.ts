// What is on screen, kept in the address bar: which library, the search, the
// filters, the sort, grid or list, and the book that is open. So back and
// forward work, a reload lands in the same place, and any view is a link.
import { useSyncExternalStore } from 'react'

export type Mode = 'grid' | 'list'

export interface ViewState {
  library: string // '' is the server's default
  q: string // what was typed in the search box
  filters: string[] // search expressions from the sidebar, all must match
  sort: string // '' is the default, date added
  order: 'asc' | 'desc'
  vl: string // a virtual library's name
  mode: Mode
  book: number | null
}

const DEFAULTS: ViewState = {
  library: '',
  q: '',
  filters: [],
  sort: '',
  order: 'desc',
  vl: '',
  mode: 'grid',
  book: null,
}

function parse(search: string): ViewState {
  const p = new URLSearchParams(search)
  const book = Number(p.get('book'))
  return {
    library: p.get('library') ?? '',
    q: p.get('q') ?? '',
    filters: p.getAll('f').filter(Boolean),
    sort: p.get('sort') ?? '',
    order: p.get('order') === 'asc' ? 'asc' : 'desc',
    vl: p.get('vl') ?? '',
    mode: p.get('view') === 'list' ? 'list' : 'grid',
    book: Number.isInteger(book) && book > 0 ? book : null,
  }
}

function serialize(s: ViewState): string {
  const p = new URLSearchParams()
  if (s.library) p.set('library', s.library)
  if (s.vl) p.set('vl', s.vl)
  if (s.q) p.set('q', s.q)
  for (const f of s.filters) p.append('f', f)
  if (s.sort) p.set('sort', s.sort)
  if (s.sort && s.order === 'asc') p.set('order', 'asc')
  if (s.mode !== 'grid') p.set('view', s.mode)
  if (s.book) p.set('book', String(s.book))
  const q = p.toString()
  return location.pathname + (q ? '?' + q : '')
}

let current = parse(location.search)
const listeners = new Set<() => void>()

window.addEventListener('popstate', () => {
  current = parse(location.search)
  listeners.forEach((f) => f())
})

function subscribe(f: () => void) {
  listeners.add(f)
  return () => listeners.delete(f)
}

export function useView(): ViewState {
  return useSyncExternalStore(subscribe, () => current)
}

/**
 * Change the view. `replace` for what should not become a step of its own
 * in the history, such as each letter typed into the search box.
 */
export function setView(change: Partial<ViewState>, { replace = false } = {}) {
  current = { ...current, ...change }
  const url = serialize(current)
  if (replace) history.replaceState(null, '', url)
  else history.pushState(null, '', url)
  listeners.forEach((f) => f())
}

/** A new library, virtual library or set of filters starts from the top. */
export function resetFor(change: Partial<ViewState>): Partial<ViewState> {
  return { book: null, ...change }
}

export { DEFAULTS }

// Searches {{{

/** The one search expression calibre gets: the box and every filter. */
export function combinedSearch(s: Pick<ViewState, 'q' | 'filters'>): string {
  const parts = [s.q.trim(), ...s.filters].filter(Boolean)
  if (parts.length < 2) return parts[0] ?? ''
  return parts.map((p) => `(${p})`).join(' and ')
}

/**
 * What a filter's chip says. The sidebar's items carry the exact expression
 * calibre should search for, so the label is read back out of it.
 */
export function filterLabel(expr: string): string {
  let m = /^[#@\w]+:"=\.?((?:[^"\\]|\\.)*)"$/.exec(expr)
  if (m) return m[1].replace(/\\(.)/g, '$1')
  m = /^rating:(\d)$/.exec(expr)
  if (m) return '★'.repeat(Number(m[1]))
  m = /^[#\w]+:>=(\d{4})-(\d{2})-01 and /.exec(expr)
  if (m)
    return m[2] === '01' && expr.includes(`${Number(m[1]) + 1}-01-01`)
      ? m[1]
      : `${m[1]}-${m[2]}`
  return expr
}

/** A search for one value of a field, the way the sidebar writes it. */
export function fieldSearch(field: string, value: string): string {
  return `${field}:"=${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
}

// }}}
