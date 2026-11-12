// How values from calibre are shown.

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const yearFormat = new Intl.DateTimeFormat(undefined, { year: 'numeric' })
const numberFormat = new Intl.NumberFormat()

/**
 * calibre's "no date": 0101-01-01, as src/pyj/date.pyj reads it, the day
 * after included for time zones. calibre's server leaves such a date out of
 * a book, but a date is never shown as the year 101 either way.
 */
export function isUndefinedDate(d: Date): boolean {
  const y = d.getUTCFullYear()
  return y < 101 || (y === 101 && d.getUTCMonth() === 0 && d.getUTCDate() <= 2)
}

/** A date to show, or undefined for none, a broken one or calibre's "no date". */
function shown(date: string | Date | undefined): Date | undefined {
  if (!date) return undefined
  const d = date instanceof Date ? date : new Date(date)
  return Number.isNaN(d.getTime()) || isUndefinedDate(d) ? undefined : d
}

/** A date from calibre's ISO text, or one the browser keeps as a Date. */
export function formatDate(date: string | Date | undefined): string {
  const d = shown(date)
  return d ? dateFormat.format(d) : ''
}

export function formatYear(date: string | Date | undefined): string {
  const d = shown(date)
  return d ? yearFormat.format(d) : ''
}

export function formatCount(n: number): string {
  return numberFormat.format(n)
}

/** A count and its noun: "1 book", "1,204 books". */
export function plural(n: number, one: string, many = one + 's'): string {
  return `${formatCount(n)} ${n === 1 ? one : many}`
}

export function books(n: number): string {
  return plural(n, 'book')
}

/** A book's authors, as the app lists them. */
export function authors(list: readonly string[] | undefined): string {
  return list?.join(', ') ?? ''
}

/**
 * A rating, which calibre keeps out of 10, a star being 2: "3 stars",
 * "1 star", "2.5 stars". With `outOfFive`, "3 out of 5 stars", for a
 * picture of the stars.
 */
export function stars(rating: number, { outOfFive = false } = {}): string {
  const n = rating / 2
  if (outOfFive) return `${n} out of 5 stars`
  return `${n} ${n === 1 ? 'star' : 'stars'}`
}

export function formatSize(bytes: number | undefined): string {
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = bytes
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v < 10 && i > 0 ? v.toFixed(1) : Math.round(v)} ${units[i]}`
}

/**
 * Where a book sits in its series: "3", "3.5", "3.25". calibre keeps two
 * decimals, and so does this, without the zeros it does not need.
 */
export function seriesIndex(index: number): string {
  return String(Number(index.toFixed(2)))
}

/** A series and where the book sits in it: "Discworld 3", "Discworld 3.5". */
export function seriesText(
  series: string | undefined,
  index: number | undefined,
): string {
  if (!series) return ''
  if (index === undefined || index === null) return series
  return `${series} ${seriesIndex(index)}`
}

/** The browser tab's title: what the page is, then "Calibre Zen". */
export function pageTitle(...parts: (string | undefined)[]): string {
  return [...parts.filter(Boolean), 'Calibre Zen'].join(' · ')
}
