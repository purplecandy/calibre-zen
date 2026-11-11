// Every query key in the app, in one place. A query is defined with one of
// these, and a write brings the cache up to date by invalidating one of
// these, so the two can never drift apart. Each key starts with what it is
// about, so invalidating a prefix (`keys.books.all()`) reaches every page of
// every list.
import type { BookQuery } from '../api'

export const keys = {
  server: () => ['server'] as const,
  library: (library: string) => ['library', library] as const,

  books: {
    all: () => ['books'] as const,
    page: (q: BookQuery, page: number) => ['books', q, page] as const,
  },
  book: {
    all: (library: string) => ['book', library] as const,
    one: (library: string, id: number) => ['book', library, id] as const,
  },
  browse: {
    all: (library: string) => ['browse', library] as const,
    field: (library: string, field: string, vl: string) =>
      ['browse', library, field, vl] as const,
  },

  canEdit: (library: string) => ['can-edit', library] as const,
  fieldNames: {
    all: (library: string) => ['field-names', library] as const,
    one: (library: string, field: string) =>
      ['field-names', library, field] as const,
  },
  note: (library: string, field: string, value: string) =>
    ['note', library, field, value] as const,

  conversion: (library: string, id: number, input: string, output: string) =>
    ['conversion', library, id, input, output] as const,
  conversionJob: (library: string, job: number) =>
    ['conversion-job', library, job] as const,

  fts: {
    all: () => ['fts'] as const,
    search: (query: unknown) => ['fts', query] as const,
    snippets: (query: unknown, ids: readonly number[]) =>
      ['fts-snippets', query, ids] as const,
  },

  deviceBooks: () => ['device-books'] as const,
}
