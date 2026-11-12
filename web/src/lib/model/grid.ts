// The cover grid's shape for a width.

/** Columns and tile size for a width: as many tiles as fit at a comfortable size. */
export function gridGeometry(width: number) {
  const small = width < 560
  const gap = small ? 12 : 20
  const min = small ? 100 : 144
  const cols = Math.max(2, Math.floor((width + gap) / (min + gap)))
  const tile = Math.max(1, (width - gap * (cols - 1)) / cols)
  // The cover, a gap, two lines of title and one of authors.
  const row = Math.round(tile * 1.5 + 8 + 52 + gap)
  return { cols, tile, gap, row }
}
