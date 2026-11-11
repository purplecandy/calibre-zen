// What is on screen, kept in the address bar: which library, the search, the
// filters, the sort, grid or list, and the book that is open. So back and
// forward work, a reload lands in the same place, and any view is a link.
import { createStore } from './store'
import { readAddress, writeAddress } from './url'

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
  edit: boolean // the open book's editor is over its details
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
  edit: false,
}

function parse(): ViewState {
  const p = readAddress()
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
    edit: p.get('edit') === '1',
  }
}

/** The address's parameters, in this order; empty ones are left out. */
function serialize(s: ViewState) {
  return {
    library: s.library,
    vl: s.vl,
    q: s.q,
    f: s.filters,
    sort: s.sort,
    order: s.sort && s.order === 'asc' ? 'asc' : undefined,
    view: s.mode !== 'grid' ? s.mode : undefined,
    book: s.book ?? undefined,
    edit: s.book && s.edit ? '1' : undefined,
  }
}

const view = createStore(parse())

window.addEventListener('popstate', () => view.set(parse()))

export function useView(): ViewState {
  return view.use()
}

/**
 * Change the view. `replace` for what should not become a step of its own
 * in the history, such as each letter typed into the search box.
 */
export function setView(
  change: Partial<ViewState>,
  { replace = false, step }: { replace?: boolean; step?: string } = {},
) {
  // Editing is a moment, not a place: any other change leaves it.
  const next = { ...view.get(), edit: false, ...change }
  writeAddress(serialize(next), { replace, state: step ? { step } : null })
  view.set(next)
}

/**
 * Open something over the page as a step of its own: a book's details, the
 * editor. The step is marked in the history, so closing it goes Back.
 */
export function openStep(step: string, change: Partial<ViewState>) {
  setView(change, { step })
}

/**
 * Close what `openStep(step)` opened: Back, when this page pushed it. When
 * it came from a link or a reload of another step, there is nothing of ours
 * to go back to, so `change` is applied in place instead.
 */
export function closeStep(step: string, change: Partial<ViewState>) {
  const state: unknown = history.state
  const ours =
    typeof state === 'object' &&
    state !== null &&
    (state as { step?: unknown }).step === step
  if (ours) history.back()
  else setView(change, { replace: true })
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
