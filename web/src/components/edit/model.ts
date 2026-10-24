// Which of a book's fields can be edited, which editor each one gets, and
// how a value goes from book_as_json to the form and from the form to
// calibre's set-fields. The same choices as calibre's own edit panel
// (src/pyj/book_list/edit_metadata.pyj), in a fixed order.
import type { Book, FieldMetadata, LibraryInfo } from '@/lib/api'

export type Kind =
  | 'text' // one line
  | 'names' // a list: authors, tags, languages, a multiple text column
  | 'series'
  | 'date'
  | 'rating'
  | 'enum'
  | 'bool'
  | 'number'
  | 'identifiers'
  | 'html' // formatted text
  | 'long-text' // plain text over several lines
  | 'markdown'

export interface FieldSpec {
  field: string
  name: string
  kind: Kind
  fm: FieldMetadata
  /** Suggest values the library already has. */
  suggest: boolean
  /** For names: what separates them when typed, and when shown. */
  separator?: string
  /** For numbers. */
  integer?: boolean
  /** For ratings. */
  halfStars?: boolean
  /** For enums. */
  values?: string[]
  /** Shown across the whole form, below the short fields. */
  wide?: boolean
}

// Never edited here: worked out by calibre, shown elsewhere, or not a field.
const IGNORED = new Set([
  'sort',
  'uuid',
  'id',
  'urls_from_identifiers',
  'lang_names',
  'last_modified',
  'path',
  'marked',
  'size',
  'ondevice',
  'cover',
  'au_map',
  'isbn',
  'in_tag_browser',
  'formats', // the Files section
])

// The built-in fields first, in the order people think of a book.
const FIRST = [
  'title',
  'authors',
  'series',
  'tags',
  'rating',
  'publisher',
  'pubdate',
  'languages',
  'identifiers',
  'timestamp',
  'pages',
]

export const UNDEFINED_DATE = '0101-01-01T00:00:00+00:00'

function editable(field: string, fm: FieldMetadata | undefined): boolean {
  if (!fm || !fm.datatype || fm.kind !== 'field') return false
  if (fm.datatype === 'composite') return false
  if (IGNORED.has(field) || field.startsWith('@')) return false
  if (field.endsWith('_sort')) return false
  if (field.endsWith('_index')) return false // the series' number goes with it
  return true
}

function spec(field: string, fm: FieldMetadata): FieldSpec {
  const name =
    field === 'timestamp'
      ? 'Date added'
      : field === 'pubdate'
        ? 'Published'
        : fm.name || field
  const display = (fm.display ?? {}) as Record<string, unknown>
  const base = { field, name, fm, suggest: false }
  if (field === 'identifiers') return { ...base, kind: 'identifiers' }
  if (field === 'comments' || fm.datatype === 'comments') {
    const as = display.interpret_as
    if (as === 'short-text') return { ...base, kind: 'text' }
    if (as === 'long-text') return { ...base, kind: 'long-text', wide: true }
    if (as === 'markdown') return { ...base, kind: 'markdown', wide: true }
    return { ...base, kind: 'html', wide: true }
  }
  switch (fm.datatype) {
    case 'series':
      return { ...base, kind: 'series', suggest: true }
    case 'datetime':
      return { ...base, kind: 'date' }
    case 'rating':
      return { ...base, kind: 'rating', halfStars: !!display.allow_half_stars }
    case 'enumeration':
      return {
        ...base,
        kind: 'enum',
        values: (display.enum_values as string[] | undefined) ?? [],
      }
    case 'bool':
      return { ...base, kind: 'bool' }
    case 'int':
    case 'float':
      return { ...base, kind: 'number', integer: fm.datatype === 'int' }
  }
  if (fm.is_multiple?.ui_to_list) {
    return {
      ...base,
      kind: 'names',
      suggest: true,
      separator: fm.is_multiple.ui_to_list,
    }
  }
  return { ...base, kind: 'text', suggest: !!fm.is_category }
}

/** The fields the form shows for this library, short ones first. */
export function editableFields(info: LibraryInfo): FieldSpec[] {
  const fm = info.field_metadata
  const order = [
    ...FIRST,
    ...info.book_display_fields,
    ...Object.keys(fm).sort((a, b) =>
      (fm[a].name || a).localeCompare(fm[b].name || b),
    ),
  ]
  const seen = new Set<string>()
  const specs: FieldSpec[] = []
  for (const field of order) {
    if (seen.has(field)) continue
    seen.add(field)
    if (editable(field, fm[field])) specs.push(spec(field, fm[field]))
  }
  // Short fields, then the book's description, then other long text.
  const rank = (s: FieldSpec) => (!s.wide ? 0 : s.field === 'comments' ? 1 : 2)
  return specs.sort((a, b) => rank(a) - rank(b))
}

// Values {{{

export interface SeriesValue {
  name: string
  index: string
}

export type FormValue =
  string | string[] | SeriesValue | number | [string, string][]

/** YYYY-MM-DD in this browser's time zone, as calibre's app shows dates. */
export function dateInput(iso: unknown): string {
  if (typeof iso !== 'string' || !iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime()) || d.getFullYear() <= 101) return ''
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

function indexText(n: unknown): string {
  const v = typeof n === 'number' ? n : 1
  return String(Number(v.toFixed(2)))
}

/** What the form starts with for `s`. */
export function initialValue(s: FieldSpec, book: Book): FormValue {
  const v = book[s.field]
  switch (s.kind) {
    case 'names': {
      const list = Array.isArray(v) ? (v as string[]) : []
      if (s.field === 'languages') {
        const names = book.lang_names ?? {}
        return list.map((code) => names[code] ?? code)
      }
      return [...list]
    }
    case 'series':
      return {
        name: typeof v === 'string' ? v : '',
        index: indexText(book[s.field + '_index']),
      }
    case 'date':
      return dateInput(v)
    case 'rating':
      return typeof v === 'number' ? v : 0
    case 'bool':
      return v === true ? 'yes' : v === false ? 'no' : ''
    case 'identifiers':
      return Object.entries((v as Record<string, string>) ?? {})
    case 'markdown':
      return String(book[s.field + '#markdown#'] ?? '')
    case 'number':
      return v === undefined || v === null ? '' : String(v)
  }
  return v === undefined || v === null ? '' : String(v)
}

export function same(a: FormValue, b: FormValue): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

/** The set-fields changes for one edited field: usually one key, two for a series. */
export function toChanges(
  s: FieldSpec,
  value: FormValue,
): Record<string, unknown> {
  switch (s.kind) {
    case 'names': {
      const seen = new Set<string>()
      const list = (value as string[])
        .map((x) => x.trim())
        .filter((x) => x && !seen.has(x) && seen.add(x))
      if (s.field === 'authors' && !list.length) return { authors: ['Unknown'] }
      return { [s.field]: list }
    }
    case 'series': {
      const { name, index } = value as SeriesValue
      const n = Number.parseFloat(index)
      return {
        [s.field]: name.trim(),
        [s.field + '_index']: Number.isFinite(n) ? n : 1,
      }
    }
    case 'date':
      return {
        [s.field]: value ? `${value as string}T12:00:00+00:00` : UNDEFINED_DATE,
      }
    case 'rating':
      return { [s.field]: value as number }
    case 'bool':
      return {
        [s.field]: value === 'yes' ? true : value === 'no' ? false : null,
      }
    case 'number': {
      const t = (value as string).trim()
      if (!t) return { [s.field]: null }
      const n = s.integer ? Number.parseInt(t, 10) : Number.parseFloat(t)
      return { [s.field]: Number.isFinite(n) ? n : null }
    }
    case 'identifiers': {
      const ids: Record<string, string> = {}
      for (const [k, v] of value as [string, string][]) {
        if (k.trim() && v.trim()) ids[k.trim().toLowerCase()] = v.trim()
      }
      return { identifiers: ids }
    }
    case 'enum':
      return { [s.field]: (value as string) || null }
  }
  const text = value as string
  if (s.field === 'title') return { title: text.trim() || 'Unknown' }
  return { [s.field]: text }
}

// }}}
