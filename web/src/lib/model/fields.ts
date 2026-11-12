// calibre's built-in fields, and what each part of the app does with them:
// whether a book's details list it, whether the editor offers it, which way
// a sort by it starts, and which fields come first. One table, so a field is
// looked up in one place and the lists cannot drift apart.

interface Role {
  /** Listed under a book's Details. Its header, its files and calibre's bookkeeping are not. */
  listed?: false
  /** Offered in the editor. Worked out by calibre, shown elsewhere, or not a field, it is not. */
  edited?: false
  /** A sort by it starts newest or highest first. */
  descending?: true
}

const ROLES: Record<string, Role> = {
  title: { listed: false },
  authors: { listed: false },
  series: { listed: false },
  series_index: { listed: false },
  rating: { listed: false, descending: true },
  comments: { listed: false },
  author_sort: { listed: false },
  formats: { listed: false, edited: false }, // the Files section
  id: { listed: false, edited: false, descending: true },
  uuid: { listed: false, edited: false },
  path: { listed: false, edited: false },
  sort: { listed: false, edited: false },
  size: { listed: false, edited: false, descending: true },
  last_modified: { listed: false, edited: false, descending: true },
  cover: { listed: false, edited: false },
  marked: { listed: false, edited: false },
  ondevice: { listed: false, edited: false },
  in_tag_browser: { listed: false, edited: false },
  timestamp: { descending: true },
  pubdate: { descending: true },
  urls_from_identifiers: { edited: false },
  lang_names: { edited: false },
  au_map: { edited: false },
  isbn: { edited: false },
}

function role(field: string): Role {
  return Object.hasOwn(ROLES, field) ? ROLES[field] : {}
}

/** Whether a book's details list this field under Details. */
export function isListed(field: string): boolean {
  return role(field).listed !== false
}

/** Whether the editor may offer this field. Its datatype decides the rest. */
export function isEdited(field: string): boolean {
  return role(field).edited !== false
}

/** Which way a sort by this field starts. */
export function sortOrder(field: string): 'asc' | 'desc' {
  return role(field).descending ? 'desc' : 'asc'
}

/** The library's sort when none is chosen: newest added first. */
export const DEFAULT_SORT = 'timestamp'

/** The editor's first fields, in the order people think of a book. */
export const EDIT_ORDER = [
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

/** The fields whose notes come first. */
export const NOTE_ORDER = ['authors', 'series', 'tags', 'publisher']

/** Where `field` comes in `order`; one it does not list comes last. */
export function rank(order: readonly string[], field: string): number {
  const i = order.indexOf(field)
  return i < 0 ? order.length : i
}
