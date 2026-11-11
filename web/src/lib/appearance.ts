// Light, dark or dim, and which colour scheme: the same choices as the
// desktop's appearance menu, kept in this browser. The first paint is set by
// the inline script in AppLayout.astro, which reads the same key.

export const KEY = 'zen-appearance'
export const SCHEMES = [
  'neutral',
  'stone',
  'zinc',
  'olive',
  'mist',
  'zen',
] as const
export const MODES = ['system', 'light', 'dark', 'dim'] as const

export type Scheme = (typeof SCHEMES)[number]
export type Mode = (typeof MODES)[number]
export interface Appearance {
  mode: Mode
  scheme: Scheme
}

export function load(): Appearance {
  let saved: Partial<Appearance> = {}
  try {
    saved = JSON.parse(localStorage.getItem(KEY) ?? '{}')
  } catch {
    // private window or blocked storage: the defaults
  }
  return {
    mode: MODES.includes(saved.mode as Mode) ? (saved.mode as Mode) : 'system',
    scheme: SCHEMES.includes(saved.scheme as Scheme)
      ? (saved.scheme as Scheme)
      : 'neutral',
  }
}

export function apply(a: Appearance): void {
  const root = document.documentElement
  const dark =
    a.mode === 'dark' ||
    a.mode === 'dim' ||
    (a.mode === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  root.dataset.scheme = a.scheme
  root.classList.toggle('dark', dark)
  root.classList.toggle('dim', a.mode === 'dim')
  const bg = getComputedStyle(root).getPropertyValue('--background').trim()
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', bg || '#ffffff')
}

export function save(a: Appearance): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(a))
  } catch {
    // not kept, but still applied
  }
  apply(a)
}
