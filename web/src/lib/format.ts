// How values from calibre are shown.

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const yearFormat = new Intl.DateTimeFormat(undefined, { year: 'numeric' })
const numberFormat = new Intl.NumberFormat()

export function formatDate(iso: string | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : dateFormat.format(d)
}

export function formatYear(iso: string | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : yearFormat.format(d)
}

export function formatCount(n: number): string {
  return numberFormat.format(n)
}

export function books(n: number): string {
  return `${formatCount(n)} ${n === 1 ? 'book' : 'books'}`
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

/** A series and where the book sits in it: "Discworld 3", "Discworld 3.5". */
export function seriesText(
  series: string | undefined,
  index: number | undefined,
): string {
  if (!series) return ''
  if (index === undefined || index === null) return series
  return `${series} ${Number.isInteger(index) ? index : index.toFixed(1)}`
}
