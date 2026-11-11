// This browser's localStorage, for what a person chose. It can be missing
// (a private window, blocked storage) or full, and a value in it may come
// from another version or be written by hand: every read can fall back, and
// every write may not be kept, without the page noticing.

/** A JSON value, if it is there and `valid` accepts it. */
export function readJson<T>(
  key: string,
  valid: (v: unknown) => v is T,
): T | undefined {
  try {
    const raw = localStorage.getItem(key)
    const v: unknown = raw === null ? undefined : JSON.parse(raw)
    return valid(v) ? v : undefined
  } catch {
    return undefined
  }
}

/** Keep a value as JSON. If it cannot be kept, it is used while the page is open. */
export function writeJson(key: string, value: unknown): void {
  writeText(key, JSON.stringify(value))
}

/** A value kept as plain text, as calibre keeps some of its own. */
export function readText(key: string): string | undefined {
  try {
    return localStorage.getItem(key) ?? undefined
  } catch {
    return undefined
  }
}

export function writeText(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // not kept, but used for as long as the page is open
  }
}

export function remove(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // nothing to do
  }
}
