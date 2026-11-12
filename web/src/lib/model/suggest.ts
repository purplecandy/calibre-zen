// Which of a field's values to suggest for what has been typed.

/** How many suggestions are shown at once. */
const SHOWN = 8

/** Values starting with `text` first, then those containing it. */
export function match(
  names: readonly string[],
  text: string,
  skip: ReadonlySet<string>,
): string[] {
  const q = text.trim().toLowerCase()
  if (!q) return []
  const starts: string[] = []
  const contains: string[] = []
  for (const n of names) {
    if (skip.has(n)) continue
    const l = n.toLowerCase()
    if (l === q) continue
    if (l.startsWith(q)) starts.push(n)
    else if (contains.length < SHOWN && l.includes(q)) contains.push(n)
    if (starts.length >= SHOWN) break
  }
  return [...starts, ...contains].slice(0, SHOWN)
}
